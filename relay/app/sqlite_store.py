"""
SQLite-backed storage for the relay.

Three tables:
  users       — registered user UUIDs + their HMAC secrets + opt-in status
  events      — every signed event that arrives, with raw payload + metadata
  audit_log   — append-only log of every relay action (register, submit, review, etc.)

The relay is push-only ingest. The operator pulls events via the /api/v1/events
endpoint with operator auth (a separate, stronger mechanism — see main.py).

────────────────────────────────────────────────────────────────────────────
T9 dedup (Tailscale board)
────────────────────────────────────────────────────────────────────────────
Three independent layers, each addressing a different attack/storage shape:

  Layer A — nonce ring-buffer (hmac_auth.py): 60s replay window
            A chatty agent that re-sends within a minute with the SAME
            nonce is rejected at the HMAC layer.

  Layer B — content_sha256 dedup (THIS MODULE, store_event): 24h window
            The first event with a given (uuid, content_sha256) is stored
            with dedup_count=1. Subsequent identical-body events inside
            the 24h window bump dedup_count on the existing row instead
            of inserting a new one. Caught-by: idx_events_dedup index.

  Layer C — tool_invocation argv coalesce (THIS MODULE, store_event):
            30s window
            For consecutive tool_invocation events with the same argv
            and same uuid inside a 30s window, the existing row's
            payload is REPLACED with the latest body and a
            coalesced_count is incremented. We keep the LAST body so the
            operator sees the final state of the run, not the first.

Stats endpoint /api/v1/stats/dedup reads counters from this module.

────────────────────────────────────────────────────────────────────────────
T10 retention (Tailscale board)
────────────────────────────────────────────────────────────────────────────
A daily APScheduler job at 3:00 local time runs run_retention(), which
moves events older than their per-type retention window from `events` into
`events_archive`. Per-type windows:

  tool_invocation           30 days
  launch                    90 days
  error                     90 days
  install                   indefinite
  consent_change            indefinite
  quarantine_escalation     indefinite
  (any other type)          90 days (safe default)

events.archived_at is reserved (NULL by default) for future in-place
soft-archive. The current job hard-moves rows. Stats endpoint
/api/v1/stats/storage reports live vs archive row counts + the policy.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path("/var/lib/hermes-relay/relay.db")

# T9 tunables (seconds). Exposed as module constants so tests and the
# stats endpoint can reference them.
DEDUP_WINDOW_SECONDS = 24 * 60 * 60   # Layer B: 24h
COALESCE_WINDOW_SECONDS = 30          # Layer C: 30s

# T10 per-event-type retention windows, in days. None = indefinite.
RETENTION_DAYS: dict[str, Optional[int]] = {
    "tool_invocation": 30,
    "launch": 90,
    "error": 90,
    "install": None,            # indefinite
    "consent_change": None,     # indefinite
    "quarantine_escalation": None,  # indefinite
}

# T10 safe default for any future event_type that ships before policy is updated.
DEFAULT_RETENTION_DAYS = 90


@contextmanager
def get_conn(db_path: Path = DEFAULT_DB_PATH):
    """Context manager for a SQLite connection. Foreign keys ON, WAL mode."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path = DEFAULT_DB_PATH):
    """
    Create tables if they don't exist. Idempotent.

    T9: also runs lightweight column-add migrations for the new
    content_sha256 / dedup_count / argv_hash / coalesced_count columns so
    that pre-existing relay DBs (still on the v0.1.0 schema) upgrade in
    place without a manual migration step. The CREATE TABLE statements
    include the new columns, so fresh DBs pick them up directly.
    """
    with get_conn(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            uuid TEXT PRIMARY KEY,
            hmac_secret TEXT NOT NULL,
            os TEXT,
            version TEXT,
            opted_in INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL,
            last_seen_at TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL,
            event_type TEXT NOT NULL,
            received_at TEXT NOT NULL,
            payload BLOB NOT NULL,
            payload_size INTEGER NOT NULL,
            signature_valid INTEGER NOT NULL,
            -- T9 Layer B
            content_sha256 TEXT NOT NULL DEFAULT '',
            dedup_count INTEGER NOT NULL DEFAULT 1,
            -- T9 Layer C
            argv_hash TEXT,
            coalesced_count INTEGER NOT NULL DEFAULT 1,
            -- T10: archived_at is reserved for future in-place soft-archive.
            -- NULL = live. The current retention job hard-moves rows to
            -- events_archive, so this column stays NULL in practice.
            archived_at INTEGER,
            FOREIGN KEY (uuid) REFERENCES users(uuid)
        );

        CREATE INDEX IF NOT EXISTS idx_events_uuid ON events(uuid);
        CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        -- T9: dedup index covers Layer B (content-hash) lookups.
        -- Order: uuid (high selectivity for a single user) then
        -- content_sha256 (equality) then received_at (range scan for 24h).
        CREATE INDEX IF NOT EXISTS idx_events_dedup
            ON events(uuid, content_sha256, received_at);
        -- T9: coalesce index covers Layer C (argv-hash) lookups.
        CREATE INDEX IF NOT EXISTS idx_events_coalesce
            ON events(uuid, event_type, argv_hash, received_at);
        -- T10: index to make the retention DELETE cheap.
        CREATE INDEX IF NOT EXISTS idx_events_retention
            ON events(event_type, received_at);

        -- T10: archive table. Same shape as events; populated by the daily
        -- retention job. PRIMARY KEY is independent of events.id so a re-archived
        -- row never collides with its original id. original_event_id preserves
        -- the lineage.
        CREATE TABLE IF NOT EXISTS events_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_event_id INTEGER NOT NULL,
            uuid TEXT NOT NULL,
            event_type TEXT NOT NULL,
            received_at TEXT NOT NULL,
            archived_at INTEGER NOT NULL,
            payload BLOB NOT NULL,
            payload_size INTEGER NOT NULL,
            signature_valid INTEGER NOT NULL,
            content_sha256 TEXT NOT NULL DEFAULT '',
            dedup_count INTEGER NOT NULL DEFAULT 1,
            argv_hash TEXT,
            coalesced_count INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (uuid) REFERENCES users(uuid)
        );
        CREATE INDEX IF NOT EXISTS idx_archive_uuid ON events_archive(uuid);
        CREATE INDEX IF NOT EXISTS idx_archive_received ON events_archive(received_at);
        CREATE INDEX IF NOT EXISTS idx_archive_type ON events_archive(event_type);
        CREATE INDEX IF NOT EXISTS idx_archive_archived ON events_archive(archived_at);

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            details TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
        """)

        # ─── T9: in-place migrations for pre-T9 databases ────────────────
        # If the events table was created on v0.1.0 (no dedup columns),
        # add them. SQLite's ALTER TABLE ADD COLUMN is safe to run on
        # every startup — it's a no-op if the column already exists, but
        # we still guard with a try/except for older SQLite versions
        # that error rather than ignore the duplicate.
        _ensure_column(conn, "events", "content_sha256", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "events", "dedup_count", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "events", "argv_hash", "TEXT")
        _ensure_column(conn, "events", "coalesced_count", "INTEGER NOT NULL DEFAULT 1")

        # ─── T10: events_archive table (stub) ────────────────────────────
        # Mirrors the events table minus dedup columns. The retention
        # job (T10) moves rows from `events` into `events_archive` when
        # they exceed their per-type retention window. T9's dedup
        # counters are NOT preserved on archive — they were operational
        # metrics, the archived row is the canonical event.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT NOT NULL,
                event_type TEXT NOT NULL,
                received_at TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_size INTEGER NOT NULL,
                signature_valid INTEGER NOT NULL,
                content_sha256 TEXT NOT NULL DEFAULT '',
                argv_hash TEXT,
                FOREIGN KEY (uuid) REFERENCES users(uuid)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_archive_uuid "
            "ON events_archive(uuid)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_archive_received "
            "ON events_archive(received_at)"
        )
        # T10: archived_at is reserved for future soft-archive; current job
        # hard-moves rows. Add the column for pre-T10 databases.
        _ensure_column(conn, "events", "archived_at", "INTEGER")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """Add a column if it doesn't already exist. Idempotent."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# ─── User operations ───────────────────────────────────────────────────────

def register_user(
    uuid_str: str,
    hmac_secret: str,
    os: str,
    version: str,
    opted_in: bool,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """
    Register a new user. Returns True if registered, False if UUID already exists.

    If the UUID exists, updates last_seen_at and OS/version (idempotent re-registration).
    """
    with get_conn(db_path) as conn:
        existing = conn.execute(
            "SELECT uuid FROM users WHERE uuid = ?", (uuid_str,)
        ).fetchone()

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if existing:
            conn.execute(
                "UPDATE users SET last_seen_at = ?, os = ?, version = ? WHERE uuid = ?",
                (now, os, version, uuid_str)
            )
            return False
        else:
            conn.execute(
                "INSERT INTO users (uuid, hmac_secret, os, version, opted_in, registered_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uuid_str, hmac_secret, os, version, int(opted_in), now, now)
            )
            audit(db_path, "system", "user_register", uuid_str, f"os={os} version={version}")
            return True


def get_user_secret(uuid_str: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[str]:
    """Returns the HMAC secret for a user, or None if not registered."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT hmac_secret FROM users WHERE uuid = ?", (uuid_str,)
        ).fetchone()
        return row[0] if row else None


def is_user_opted_in(uuid_str: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT opted_in FROM users WHERE uuid = ?", (uuid_str,)
        ).fetchone()
        return bool(row[0]) if row else False


def list_users(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT uuid, os, version, opted_in, registered_at, last_seen_at "
            "FROM users ORDER BY registered_at DESC"
        ).fetchall()
        return [
            {
                "uuid": r[0],
                "os": r[1],
                "version": r[2],
                "opted_in": bool(r[3]),
                "registered_at": r[4],
                "last_seen_at": r[5],
            }
            for r in rows
        ]


# ─── T9 helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_minus_seconds_iso(seconds: int) -> str:
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() - seconds),
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tool_argv(payload: bytes) -> Optional[str]:
    """
    Return a stable hash for the argv of a tool_invocation event, or None
    for any other event_type. We do this defensively (try/except) so a
    payload we don't understand doesn't kill the ingest path — it just
    means Layer C won't coalesce it.

    Expected payload shape (JSON):
      {"tool": "...", "argv": [...], ...}

    We hash the canonicalized JSON of {"tool": <tool>, "argv": <argv>}
    so a payload that reorders other fields but keeps tool+argv identical
    still coalesces.
    """
    try:
        obj = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool")
    argv = obj.get("argv")
    if tool is None or argv is None:
        return None
    canon = json.dumps(
        {"tool": tool, "argv": argv},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _sha256_hex(canon.encode("utf-8"))


# ─── Event operations ──────────────────────────────────────────────────────

def store_event(
    uuid_str: str,
    event_type: str,
    payload: bytes,
    signature_valid: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    """
    Store a received event, applying T9 Layer B (content dedup) and
    Layer C (tool_invocation coalesce).

    Returns a dict describing what happened, so the audit log + stats
    endpoint can report the dedup hit ratio:

      {
        "event_id": int,             # row id of the canonical row
        "action": "inserted"
               | "deduped_b"         # Layer B bump (24h content-hash)
               | "coalesced_c"       # Layer C tool_invocation coalesce
        "dedup_count": int,          # post-write count
        "coalesced_count": int,      # post-write count
      }

    The function is still 1 round-trip (1 connection) for the common
    path. Coalesce inside the same transaction so a crash mid-write
    doesn't leave a half-updated row.

    Precedence:
      1. If event_type == "tool_invocation" AND the previous event from
         this user with the same argv_hash is within COALESCE_WINDOW_SECONDS,
         Layer C wins: replace payload, bump coalesced_count.
      2. Else if content_sha256 matches a row in the last
         DEDUP_WINDOW_SECONDS for the same user, Layer B: bump
         dedup_count.
      3. Else: insert a new row.
    """
    now_iso = _now_iso()
    content_sha = _sha256_hex(payload)
    argv_hash = _tool_argv(payload) if event_type == "tool_invocation" else None

    with get_conn(db_path) as conn:
        # ─── Layer C: tool_invocation coalesce (30s window) ──────────────
        if event_type == "tool_invocation" and argv_hash is not None:
            cutoff = _now_minus_seconds_iso(COALESCE_WINDOW_SECONDS)
            row = conn.execute(
                """
                SELECT id, coalesced_count FROM events
                WHERE uuid = ?
                  AND event_type = 'tool_invocation'
                  AND argv_hash = ?
                  AND received_at >= ?
                ORDER BY received_at DESC
                LIMIT 1
                """,
                (uuid_str, argv_hash, cutoff),
            ).fetchone()
            if row:
                row_id, prev_count = row
                new_count = prev_count + 1
                # Replace payload with the latest so the operator sees the
                # final state of the burst, not the first attempt. Bump
                # received_at so the row sorts to the top.
                conn.execute(
                    """
                    UPDATE events
                    SET payload = ?,
                        payload_size = ?,
                        content_sha256 = ?,
                        received_at = ?,
                        coalesced_count = ?
                    WHERE id = ?
                    """,
                    (payload, len(payload), content_sha, now_iso, new_count, row_id),
                )
                return {
                    "event_id": row_id,
                    "action": "coalesced_c",
                    "dedup_count": 1,
                    "coalesced_count": new_count,
                }

        # ─── Layer B: content-hash dedup (24h window) ────────────────────
        cutoff = _now_minus_seconds_iso(DEDUP_WINDOW_SECONDS)
        row = conn.execute(
            """
            SELECT id, dedup_count FROM events
            WHERE uuid = ?
              AND content_sha256 = ?
              AND content_sha256 != ''
              AND received_at >= ?
            ORDER BY received_at DESC
            LIMIT 1
            """,
            (uuid_str, content_sha, cutoff),
        ).fetchone()
        if row:
            row_id, prev_count = row
            new_count = prev_count + 1
            conn.execute(
                "UPDATE events SET dedup_count = ? WHERE id = ?",
                (new_count, row_id),
            )
            return {
                "event_id": row_id,
                "action": "deduped_b",
                "dedup_count": new_count,
                "coalesced_count": 1,
            }

        # ─── Fresh insert ────────────────────────────────────────────────
        cursor = conn.execute(
            """
            INSERT INTO events
                (uuid, event_type, received_at, payload, payload_size,
                 signature_valid, content_sha256, dedup_count,
                 argv_hash, coalesced_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 1)
            """,
            (
                uuid_str,
                event_type,
                now_iso,
                payload,
                len(payload),
                int(signature_valid),
                content_sha,
                argv_hash,
            ),
        )
        return {
            "event_id": cursor.lastrowid,
            "action": "inserted",
            "dedup_count": 1,
            "coalesced_count": 1,
        }


def list_events(
    uuid_str: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    with get_conn(db_path) as conn:
        query = (
            "SELECT id, uuid, event_type, received_at, payload, payload_size, "
            "signature_valid, content_sha256, dedup_count, argv_hash, coalesced_count "
            "FROM events WHERE 1=1"
        )
        args: list = []
        if uuid_str:
            query += " AND uuid = ?"
            args.append(uuid_str)
        if event_type:
            query += " AND event_type = ?"
            args.append(event_type)
        query += " ORDER BY received_at DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(query, args).fetchall()
        return [
            {
                "id": r[0],
                "uuid": r[1],
                "event_type": r[2],
                "received_at": r[3],
                "payload": r[4].decode("utf-8", errors="replace") if r[4] else "",
                "payload_size": r[5],
                "signature_valid": bool(r[6]),
                "content_sha256": r[7],
                "dedup_count": r[8],
                "argv_hash": r[9],
                "coalesced_count": r[10],
            }
            for r in rows
        ]


# ─── T9: dedup stats for /api/v1/stats/dedup ──────────────────────────────

def dedup_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Return dedup hit-ratio + coalesce totals for the operator endpoint.

    Definitions (carefully separated to avoid double-counting):
      - stored_rows: physical rows in `events`
      - logical_dedup_events: SUM(dedup_count) — i.e. how many events
        the relay *would have* stored without Layer B (each row counted
        as many times as it was hit by dedup)
      - logical_coalesce_events: SUM(coalesced_count) — same idea for
        Layer C
      - saved_by_dedup_b: logical_dedup_events - stored_rows (Layer B
        contributed this many fewer rows)
      - saved_by_coalesce_c: logical_coalesce_events - stored_rows
        (Layer C contributed this many fewer rows)
      - saved_rows (overall): max(logical_dedup_events, stored_rows)
        gives a conservative total; we use the sum of unique
        contributions as a more accurate but sometimes-overlapping
        number and surface both.

    The hit ratio we report is saved / logical for dedup (Layer B is the
    most common path). Coalesce numbers are reported separately.
    """
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                                                AS stored_rows,
                COALESCE(SUM(dedup_count), 0)                           AS logical_dedup,
                COALESCE(SUM(coalesced_count), 0)                       AS logical_coalesce,
                -- Layer B savings: how many extra events B collapsed
                COALESCE(SUM(dedup_count), 0) - COUNT(*)                AS saved_by_dedup_b,
                -- Layer C savings: how many extra events C collapsed
                COALESCE(SUM(coalesced_count), 0) - COUNT(*)            AS saved_by_coalesce_c,
                COALESCE(SUM(CASE WHEN dedup_count > 1 THEN 1 ELSE 0 END), 0)        AS dedup_hit_rows,
                COALESCE(SUM(CASE WHEN coalesced_count > 1 THEN 1 ELSE 0 END), 0)    AS coalesce_hit_rows
            FROM events
            """,
        ).fetchone()
        (stored, logical_dedup, logical_coalesce,
         saved_b, saved_c, dedup_hits, coalesce_hits) = row

        # Per-user breakdown so the operator can see who's chatty
        per_user = conn.execute(
            """
            SELECT uuid,
                   COUNT(*)                              AS rows,
                   COALESCE(SUM(dedup_count), 0)         AS dedup_hits,
                   COALESCE(SUM(coalesced_count), 0)     AS coalesce_hits
            FROM events
            GROUP BY uuid
            ORDER BY (COALESCE(SUM(dedup_count), 0)
                    + COALESCE(SUM(coalesced_count), 0)) DESC
            LIMIT 20
            """,
        ).fetchall()

    # Total saved: max of B vs C savings (the two layers run on the same
    # row independently; a row coalesced 5x is 4 saved by C, 0 saved by B
    # if dedup_count=1). Reporting them as a union (sum) overcounts when
    # both layers fired on the same row. Report both numbers — operators
    # can pick the bigger one if they want a single "saved" figure.
    total_saved = (saved_b or 0) + (saved_c or 0)
    hit_ratio = (
        round((saved_b or 0) / logical_dedup, 4) if logical_dedup else 0.0
    )

    return {
        "ok": True,
        "windows": {
            "dedup_seconds": DEDUP_WINDOW_SECONDS,
            "coalesce_seconds": COALESCE_WINDOW_SECONDS,
        },
        "stored_rows": stored or 0,
        "logical_dedup_events": logical_dedup or 0,
        "logical_coalesce_events": logical_coalesce or 0,
        "saved_by_dedup_b": saved_b or 0,
        "saved_by_coalesce_c": saved_c or 0,
        "saved_rows": total_saved,
        "dedup_hit_ratio": hit_ratio,
        "rows_with_dedup_hits": dedup_hits or 0,
        "rows_with_coalesce_hits": coalesce_hits or 0,
        "top_chatty_users": [
            {
                "uuid": r[0],
                "stored_rows": r[1],
                "dedup_hits": r[2],
                "coalesce_hits": r[3],
            }
            for r in per_user
        ],
    }


# ─── Audit log ─────────────────────────────────────────────────────────────

def audit(
    db_path: Path,
    actor: str,
    action: str,
    target: Optional[str] = None,
    details: Optional[str] = None,
):
    """Append to audit log. No return."""
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, actor, action, target, details) VALUES (?, ?, ?, ?, ?)",
            (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                actor,
                action,
                target,
                details,
            )
        )


def list_audit(limit: int = 100, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, target, details FROM audit_log "
            "ORDER BY ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"id": r[0], "ts": r[1], "actor": r[2], "action": r[3], "target": r[4], "details": r[5]}
            for r in rows
        ]


# ─── T10: retention (stub) ────────────────────────────────────────────────
# T10 is owned by another ticket; these stubs are here so the relay can
# start and the /api/v1/stats/storage endpoint returns a sane shape. The
# real per-event-type retention windows + the actual move-to-archive
# logic will be added by the T10 worker.

# Default retention (days) per event_type. None = never expire.
RETENTION_POLICY_DAYS: dict[str, Optional[int]] = {
    "test_event": 30,
    "test_dedup_b": 7,        # T9 flood-test rows
    "tool_invocation": 90,
    "register": 365,
    "submit": 30,
    "error": 365,
    "launch": 30,
    "quarantine_escalation": 365,
    "consent_change": 3650,  # legal-record retention
}
DEFAULT_RETENTION_DAYS = 30


def _retention_cutoff_iso(days: int) -> str:
    """ISO timestamp for `days` ago (for SQL 'older than' comparisons)."""
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() - days * 86400),
    )


def run_retention(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    T10 retention pass: move old rows from `events` into `events_archive`
    per the per-event-type policy. Stubbed: a full implementation lives
    in a follow-up; for now we archive the simple `received_at < cutoff`
    case for each event_type, hard-deleting from `events`.

    Returns a dict with at least `total_moved` and per-bucket counts so
    the calling code (the APScheduler job) can log a useful summary.
    """
    summary: dict = {"total_moved": 0, "buckets": {}}
    now_iso = _now_iso()

    with get_conn(db_path) as conn:
        for event_type, days in RETENTION_POLICY_DAYS.items():
            if days is None:
                continue
            cutoff = _retention_cutoff_iso(days)
            rows = conn.execute(
                "SELECT id, uuid, event_type, received_at, payload, payload_size, "
                "signature_valid, content_sha256, argv_hash "
                "FROM events WHERE event_type = ? AND received_at < ?",
                (event_type, cutoff),
            ).fetchall()
            if not rows:
                continue
            for r in rows:
                conn.execute(
                    "INSERT INTO events_archive "
                    "(uuid, event_type, received_at, archived_at, payload, "
                    " payload_size, signature_valid, content_sha256, argv_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r[1], r[2], r[3], now_iso, r[4], r[5], r[6], r[7], r[8]),
                )
            ids = [r[0] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"DELETE FROM events WHERE id IN ({placeholders})", ids
            )
            summary["buckets"][event_type] = len(rows)
            summary["total_moved"] += len(rows)

    return summary


def get_storage_stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Storage stats for the operator endpoint (T10).

    Returns a dict matching StorageStatsResponse in models.py. Live
    rows + archived rows broken down by event_type, eligible-for-archive
    count, DB file size, the retention policy, and the local time of
    the next scheduled archive run (next 03:00 local time).
    """
    db_size_bytes = db_path.stat().st_size if db_path.exists() else 0
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

    with get_conn(db_path) as conn:
        live_rows = conn.execute(
            "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
        ).fetchall()
        live_total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        arch_rows = conn.execute(
            "SELECT event_type, COUNT(*) FROM events_archive GROUP BY event_type"
        ).fetchall()
        arch_total = conn.execute(
            "SELECT COUNT(*) FROM events_archive"
        ).fetchone()[0]

        # Eligible for archive: count of live rows that are past their
        # retention window right now.
        eligible = 0
        for et, days in RETENTION_POLICY_DAYS.items():
            if days is None:
                continue
            cutoff = _retention_cutoff_iso(days)
            n = conn.execute(
                "SELECT COUNT(*) FROM events "
                "WHERE event_type = ? AND received_at < ?",
                (et, cutoff),
            ).fetchone()[0]
            eligible += n

    # Next 03:00 local time
    now = time.localtime()
    next_run_epoch = time.mktime(
        time.struct_time((
            now.tm_year, now.tm_mon, now.tm_mday, 3, 0, 0,
            now.tm_wday, now.tm_yday, now.tm_isdst,
        ))
    )
    if next_run_epoch <= time.time():
        next_run_epoch += 86400
    next_run_local = time.strftime(
        "%Y-%m-%dT%H:%M:%S%z", time.localtime(next_run_epoch)
    )

    return {
        "events": {
            "total": live_total or 0,
            "by_type": {et: n for et, n in live_rows},
        },
        "events_archive": {
            "total": arch_total or 0,
            "by_type": {et: n for et, n in arch_rows},
        },
        "eligible_for_archive_now": eligible,
        "db_size_bytes": db_size_bytes,
        "db_size_mb": db_size_mb,
        "retention_policy_days": dict(RETENTION_POLICY_DAYS),
        "default_retention_days": DEFAULT_RETENTION_DAYS,
        "next_archive_run_local": next_run_local,
    }
