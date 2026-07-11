"""
Hermes Dist relay — FastAPI application.

Endpoints:
  POST   /api/v1/register        User self-registration (no auth required)
  POST   /api/v1/submit          Signed event submission (HMAC required)
  GET    /api/v1/healthz         Health check (no auth)
  GET    /api/v1/events          List events (operator auth required)
  GET    /api/v1/users           List users (operator auth required)
  GET    /api/v1/audit           List audit log (operator auth required)
  GET    /api/v1/stats/dedup     Dedup hit-ratio + coalesce totals (operator)

Operator auth: a separate static token (env var OPERATOR_TOKEN) checked via
X-Operator-Token header. This is intentionally NOT HMAC — operators are
humans, not user installs.

────────────────────────────────────────────────────────────────────────────
T9 dedup (Tailscale board)
────────────────────────────────────────────────────────────────────────────
Three independent layers, applied in order from cheapest/most-certain
to most-specific:

  Layer A — HMAC nonce ring buffer (hmac_auth.py): 60s replay window.
            Same nonce inside 60s → 401. Catches a literal replay.

  Layer B — Content-hash dedup (sqlite_store.py): 24h window.
            Same (uuid, content_sha256) inside 24h → bump dedup_count.
            Applied in /submit after HMAC passes.

  Layer C — tool_invocation argv coalesce (sqlite_store.py): 30s window.
            Same (uuid, event_type=tool_invocation, argv_hash) inside
            30s → replace payload with the latest, bump coalesced_count.
            Layer C runs BEFORE Layer B in store_event so a noisy
            tool_invocation burst doesn't even hit the dedup index.

SubmitResponse now includes a `dedup` field showing the layer that
fired for each event, so the operator can see Layer B vs C behavior
in test output.

────────────────────────────────────────────────────────────────────────────
T10 retention (Tailscale board)
────────────────────────────────────────────────────────────────────────────
A daily APScheduler job at 3:00 local time runs
sqlite_store.run_retention(), which moves events older than their per-type
retention window from `events` into `events_archive`. The job runs in a
single worker process; an flock() on <db-dir>/.retention.lock prevents
multiple uvicorn workers from racing on the same archive. See
relay/README.md for the per-event-type windows.

Operator visibility: GET /api/v1/stats/storage.
"""

import os
import time
import secrets
import logging
from pathlib import Path

# fcntl is POSIX-only. On Windows (where devs run tests), fall back to a
# best-effort no-op lock so the same code imports cleanly. In production the
# relay runs in Linux (python:3.11-slim) where fcntl is always available.
try:
    import fcntl  # type: ignore[import-not-found]

    def _try_lock_exclusive(fd) -> bool:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
except ImportError:  # pragma: no cover — Windows / non-POSIX dev boxes
    def _try_lock_exclusive(fd) -> bool:
        # On Windows we can't atomically flock, so just always return True —
        # dev-mode test runs use RELAY_DISABLE_SCHEDULER=1 anyway.
        return True

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .models import (
    RegisterRequest, RegisterResponse,
    SubmitResponse, EventsResponse, UsersResponse, HealthResponse,
    StorageStatsResponse,
)
from . import sqlite_store
from .hmac_auth import verify_hmac_request


log = logging.getLogger("relay")


# ─── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hermes Dist Relay",
    description="Collector for hermes-dist PoC. Receives signed events from user installs.",
    version="0.1.0",
)

DB_PATH = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN", "")
# Set to "1" to disable the scheduler entirely (used by tests and by
# secondary uvicorn workers that lost the leader-election race).
DISABLE_SCHEDULER = os.environ.get("RELAY_DISABLE_SCHEDULER", "0") == "1"

START_TIME = time.time()


@app.on_event("startup")
def startup():
    sqlite_store.init_db(DB_PATH)
    if not OPERATOR_TOKEN:
        # Generate a random one and print to stdout for the operator to capture
        token = secrets.token_hex(32)
        print(f"⚠ OPERATOR_TOKEN not set. Generated random: {token}", flush=True)
        print(f"  Set this in /etc/hermes-relay/operator-token and add to .env", flush=True)
        globals()["OPERATOR_TOKEN"] = token

    _start_retention_scheduler()


@app.on_event("shutdown")
def shutdown():
    sched = globals().get("_scheduler")
    if sched is not None and sched.running:
        sched.shutdown(wait=False)


# ─── Retention scheduler (T10) ─────────────────────────────────────────────

def _retention_job():
    """The actual job: run the retention pass and log the result."""
    log.info("retention: starting daily archive pass")
    try:
        summary = sqlite_store.run_retention(db_path=DB_PATH)
        total = summary.get("total_moved", 0)
        log.info("retention: archived %d rows (%s)", total, summary)
        sqlite_store.audit(
            DB_PATH,
            actor="system",
            action="retention_run",
            target=None,
            details=f"moved={total} buckets={summary}",
        )
    except Exception:
        log.exception("retention: archive pass failed")
        sqlite_store.audit(
            DB_PATH,
            actor="system",
            action="retention_failed",
            target=None,
            details="see relay logs",
        )


def _start_retention_scheduler():
    """
    Start a single APScheduler instance and run the retention job daily at
    3:00 local time. Uvicorn is started with --workers 2 in production,
    so we use a file lock (best-effort single-leader) to make sure only
    one worker actually schedules the job - the other workers exit early
    and never start a second scheduler.

    To force-disable (e.g. for tests), set RELAY_DISABLE_SCHEDULER=1.
    """
    if DISABLE_SCHEDULER:
        log.info("retention: scheduler disabled by RELAY_DISABLE_SCHEDULER=1")
        return

    # Try to acquire an exclusive lock on a file next to the DB. The first
    # worker to start holds the lock for the life of the process; any
    # subsequent workers fail flock() and skip scheduling.
    lock_path = DB_PATH.parent / ".retention.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(lock_path, "w")
    if not _try_lock_exclusive(lock_fd):
        log.info("retention: another worker holds %s — scheduler not started here", lock_path)
        lock_fd.close()
        return

    sched = BackgroundScheduler(timezone="local")
    sched.add_job(
        _retention_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="retention_daily",
        name="relay retention (T10)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    globals()["_scheduler"] = sched
    globals()["_scheduler_lock_fd"] = lock_fd
    log.info("retention: scheduler started - daily at 3:00 local time (lock=%s)", lock_path)

    # Run once at startup so a fresh deployment doesn't have to wait until
    # tomorrow at 3:00 to archive an already-stale backlog.
    sched.add_job(
        _retention_job,
        trigger="date",
        id="retention_startup",
        name="relay retention (startup catch-up)",
        replace_existing=True,
    )


# ─── Operator auth ─────────────────────────────────────────────────────────

def require_operator(x_operator_token: str = Header(..., min_length=64, max_length=64)):
    if not OPERATOR_TOKEN:
        raise HTTPException(status_code=503, detail="Operator token not configured")
    if not secrets.compare_digest(x_operator_token, OPERATOR_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid operator token")
    return True


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/v1/healthz", response_model=HealthResponse)
def healthz():
    """Public health check. No auth required."""
    db_size = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
    with sqlite_store.get_conn(DB_PATH) as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    return HealthResponse(
        ok=True,
        version="hermes-relay-0.1.0",
        uptime_seconds=time.time() - START_TIME,
        db_size_mb=round(db_size, 2),
        user_count=user_count,
        event_count=event_count,
    )


@app.post("/api/v1/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    """
    User self-registration. No HMAC (the user does not have a secret yet).
    Returns a generated HMAC secret on first registration. The user install
    stores this and uses it for all future requests.

    Idempotent: re-registering with the same UUID returns ok=True, registered=False,
    hmac_secret=None. The user keeps their original secret.
    """
    if req.opted_in is False:
        # User opted out — record this for audit, return 200 with no secret
        # They can register again later if they change their mind
        sqlite_store.audit(DB_PATH, req.uuid, "register_opted_out", req.uuid, f"os={req.os}")
        return RegisterResponse(ok=True, registered=False, relay_version="hermes-relay-0.1.0")

    # Generate a per-user HMAC secret
    secret = secrets.token_hex(32)

    try:
        registered = sqlite_store.register_user(
            uuid_str=req.uuid,
            hmac_secret=secret,
            os=req.os,
            version=req.version,
            opted_in=req.opted_in,
            db_path=DB_PATH,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")

    if registered:
        return RegisterResponse(
            ok=True,
            registered=True,
            hmac_secret=secret,
            relay_version="hermes-relay-0.1.0",
        )
    else:
        # Already registered — don't leak the secret
        return RegisterResponse(
            ok=True,
            registered=False,
            hmac_secret=None,
            relay_version="hermes-relay-0.1.0",
        )


@app.post("/api/v1/submit", response_model=SubmitResponse)
async def submit(verified: dict = Depends(verify_hmac_request)):
    """
    HMAC-signed event submission. The verify_hmac_request dependency
    does all the signature/clock-skew/replay checking (Layer A) before
    we get here.

    store_event applies Layer B (content-hash dedup, 24h) and Layer C
    (tool_invocation argv coalesce, 30s) and returns a small dict
    describing which path fired. We surface that as `dedup` in the
    response so test scripts and operator tooling can see the layer
    that ran.
    """
    result = sqlite_store.store_event(
        uuid_str=verified["user_uuid"],
        event_type=verified["event_type"],
        payload=verified["body_bytes"],
        signature_valid=True,
        db_path=DB_PATH,
    )
    # result is now a dict: {event_id, action, dedup_count, coalesced_count}
    event_id = result["event_id"]
    sqlite_store.audit(
        DB_PATH,
        verified["user_uuid"],
        "event_received",
        str(event_id),
        f"type={verified['event_type']} size={len(verified['body_bytes'])} "
        f"dedup={result['action']} d={result['dedup_count']} c={result['coalesced_count']}",
    )
    return SubmitResponse(
        ok=True,
        event_id=event_id,
        received_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        dedup=result["action"],
        dedup_count=result["dedup_count"],
        coalesced_count=result["coalesced_count"],
    )


# ─── Operator-only endpoints ───────────────────────────────────────────────

@app.get("/api/v1/events", response_model=EventsResponse, dependencies=[Depends(require_operator)])
def list_events(
    uuid: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
):
    events = sqlite_store.list_events(uuid_str=uuid, event_type=event_type, limit=limit, db_path=DB_PATH)
    return EventsResponse(ok=True, count=len(events), events=events)


@app.get("/api/v1/users", response_model=UsersResponse, dependencies=[Depends(require_operator)])
def list_users():
    users = sqlite_store.list_users(db_path=DB_PATH)
    return UsersResponse(ok=True, count=len(users), users=users)


@app.get("/api/v1/audit", dependencies=[Depends(require_operator)])
def list_audit(limit: int = 100):
    entries = sqlite_store.list_audit(limit=limit, db_path=DB_PATH)
    return {"ok": True, "count": len(entries), "entries": entries}


@app.get(
    "/api/v1/stats/storage",
    response_model=StorageStatsResponse,
    dependencies=[Depends(require_operator)],
)
def stats_storage():
    """
    Storage stats for operators (T10).

    Returns live and archive row counts (broken down by event_type), the
    current DB file size, the number of live rows that are eligible to be
    archived right now, the per-event-type retention policy, and the local
    time of the next scheduled archive run.
    """
    return sqlite_store.get_storage_stats(db_path=DB_PATH)


@app.get("/api/v1/stats/dedup", dependencies=[Depends(require_operator)])
def stats_dedup():
    """
    Dedup stats for operators (T9).

    Returns hit-ratio + savings for Layer B (content-hash dedup, 24h)
    and Layer C (tool_invocation argv coalesce, 30s), plus a top-20
    per-user breakdown so the operator can see who's chatty.

    The hit ratio is `saved_by_dedup_b / logical_dedup_events` — i.e.
    "of the events the relay would have stored without Layer B, what
    fraction did Layer B actually skip?"

    No parameters; aggregate over all rows. Per-user / per-event-type
    breakdowns live in the response payload.
    """
    return sqlite_store.dedup_stats(db_path=DB_PATH)


# ─── Root ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "hermes-dist-relay",
        "version": "0.1.0",
        "endpoints": [
            "GET  /api/v1/healthz",
            "POST /api/v1/register",
            "POST /api/v1/submit (HMAC)",
            "GET  /api/v1/events (operator)",
            "GET  /api/v1/users  (operator)",
            "GET  /api/v1/audit  (operator)",
            "GET  /api/v1/stats/storage (operator)",
            "GET  /api/v1/stats/dedup (operator)",
        ],
    }
