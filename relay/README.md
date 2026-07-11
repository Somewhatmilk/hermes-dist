# Hermes Dist Relay

SQLite-backed collector that receives HMAC-signed events from `hermes-dist`
user installs. Designed for a single low-traffic relay node (a few thousand
events/day across the whole fleet).

## What it does

1. Users self-register (`POST /api/v1/register`) and receive a per-user HMAC
   secret.
2. Users submit signed events (`POST /api/v1/submit`) — replay, clock-skew,
   and signature checks are enforced by `app/hmac_auth.py`.
3. Events land in the SQLite `events` table.
4. A scheduled retention job (T10) moves aged-out events into
   `events_archive` so the live table stays small.
5. Operators query events / users / audit / storage via operator-token
   authenticated endpoints.

## Run it

```bash
# Build
docker build -t hermes-relay:test .

# Run with a known operator token
OPERATOR_TOKEN=$(openssl rand -hex 32)
docker run -d --rm --name hermes-relay \
    -p 127.0.0.1:9119:9119 \
    -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
    -v "$PWD/test-data:/var/lib/hermes-relay" \
    hermes-relay:test

# Health check
curl http://127.0.0.1:9119/api/v1/healthz
```

See `tests/dry-run.sh` for an end-to-end happy-path verification.

## Endpoints

| Method | Path                       | Auth      | Notes                                    |
|--------|----------------------------|-----------|------------------------------------------|
| GET    | `/api/v1/healthz`          | none      | Liveness + counts                        |
| POST   | `/api/v1/register`         | none      | Returns per-user HMAC secret on first registration |
| POST   | `/api/v1/submit`           | HMAC      | Signed event ingest                      |
| GET    | `/api/v1/events`           | operator  | Query `events` (live)                    |
| GET    | `/api/v1/users`            | operator  | List registered users                    |
| GET    | `/api/v1/audit`            | operator  | Append-only audit log                    |
| GET    | `/api/v1/stats/storage`    | operator  | Live vs archive row counts + retention policy |

Operator auth: send `X-Operator-Token: <64-hex-char-token>`. Set
`OPERATOR_TOKEN` in the environment before launching uvicorn; if unset, the
relay generates a random token and prints it to stdout on startup.

## Data model

Three live tables + one archive table (all in `relay.db`):

```
users(uuid PK, hmac_secret, os, version, opted_in, registered_at, last_seen_at)

events(id PK, uuid FK, event_type, received_at,
       payload BLOB, payload_size, signature_valid, archived_at)

events_archive(id PK, original_event_id, uuid FK, event_type, received_at,
               archived_at, payload BLOB, payload_size, signature_valid)

audit_log(id PK, ts, actor, action, target, details)
```

`events.archived_at` is reserved for future in-place soft-archive (NULL
today; populated by the retention job when it moves a row to
`events_archive`). The current job is hard-archive — rows are moved, not
soft-deleted.

## Retention policy (T10)

The relay enforces bounded retention so the live `events` table does not
grow without limit. Every day at **03:00 local time**, an APScheduler job
(`app/main.py::_start_retention_scheduler`) calls
`app/sqlite_store.py::run_retention`, which moves aged-out rows from
`events` into `events_archive`.

### Per-event-type windows

| event_type              | Retention | Why                                                                |
|-------------------------|-----------|--------------------------------------------------------------------|
| `tool_invocation`       | 30 days   | High-volume; only useful for short-window debugging + dedup stats. |
| `launch`                | 90 days   | Quarterly trend visibility.                                        |
| `error`                 | 90 days   | Quarterly incident review.                                         |
| `install`               | indefinite | Lifecycle fact; useful forever.                                   |
| `consent_change`        | indefinite | Compliance / audit trail.                                         |
| `quarantine_escalation` | indefinite | Security audit trail.                                             |
| (any other type)        | 90 days (default) | Safe fallback if a new event_type ships before policy is updated. |

### How it works

For each bucket:

```sql
BEGIN;
INSERT INTO events_archive
    (original_event_id, uuid, event_type, received_at, archived_at,
     payload, payload_size, signature_valid)
SELECT id, uuid, event_type, received_at, <now_epoch>,
       payload, payload_size, signature_valid
FROM events
WHERE event_type = ? AND received_at < ?;

DELETE FROM events
WHERE event_type = ? AND received_at < ?;
COMMIT;
```

The INSERT + DELETE are wrapped in a single explicit transaction per
bucket, so a crash mid-move leaves the database consistent (no
duplication, no silent loss).

A startup catch-up pass runs once when the relay boots, so a fresh
deployment does not have to wait until 03:00 to clear an already-stale
backlog.

### Multi-worker safety

Uvicorn is launched with `--workers 2` in production. Only one worker
must run the scheduler; otherwise both workers would race on the same
archive rows. The first worker to start takes an exclusive `flock()` on
`<db-dir>/.retention.lock`; the second worker's `flock(LOCK_EX|LOCK_NB)`
fails with `BlockingIOError` and skips scheduling. Lock is held for the
life of the process; the kernel releases it on exit.

Set `RELAY_DISABLE_SCHEDULER=1` to disable the scheduler entirely (used
by `tests/dry-run.sh` so the test container does not fire a retention
job in the middle of the test).

### Operator visibility

```bash
curl -sS -H "X-Operator-Token: $OPERATOR_TOKEN" \
    http://127.0.0.1:9119/api/v1/stats/storage | jq
```

Returns:

```json
{
  "events":          { "total": 1234, "by_type": { "tool_invocation": 800, ... } },
  "events_archive":  { "total": 5678, "by_type": { "tool_invocation": 5000, ... } },
  "eligible_for_archive_now": 200,
  "db_size_bytes":   4194304,
  "db_size_mb":      4.0,
  "retention_policy_days": {
    "tool_invocation": 30, "launch": 90, "error": 90,
    "install": null, "consent_change": null, "quarantine_escalation": null
  },
  "default_retention_days": 90,
  "next_archive_run_local": "2026-07-12T03:00:00+00:00"
}
```

`eligible_for_archive_now` is the number of live rows that the next job
will move — useful for spotting a stuck or runaway scheduler. A value
that monotonically grows across days means the job is not running.

### Out of scope (intentionally)

- **Cold storage migration.** `events_archive` lives in the same SQLite
  file as `events`. True cold-tier export (S3, parquet, etc.) is a
  follow-up ticket. The schema is designed so that a future cold-tier
  job can `SELECT … FROM events_archive WHERE archived_at < ?` without
  any schema change.
- **Per-user retention overrides.** The policy is global. If a single
  user ever needs a different window, add a `users.retention_override`
  column and a join in `run_retention`.
- **In-place soft archive.** `events.archived_at` is reserved but
  unused. The current job hard-moves rows.

## Audit trail

Every relay action writes to `audit_log`:

- `user_register`, `register_opted_out` — registration events
- `event_received` — every accepted `/submit`
- `retention_run`, `retention_failed` — system actor, written by the
  retention job

Query with `GET /api/v1/audit?limit=100`.

## Files

```
relay/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt          # fastapi, uvicorn, pydantic, httpx, apscheduler
├── README.md                 # this file
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app + APScheduler
│   ├── models.py             # pydantic request/response models
│   ├── hmac_auth.py          # HMAC verification dependency
│   └── sqlite_store.py       # schema + retention logic
├── deploy/
│   ├── relay.service         # systemd unit
│   ├── relay-ping.timer      # systemd timer (operator health pings)
│   ├── daily-ping.sh         # ping script
│   └── deploy-oracle.sh      # one-shot deploy helper
└── tests/
    ├── dry-run.sh            # end-to-end happy path
    └── fire-test-event.sh    # single signed test event
```