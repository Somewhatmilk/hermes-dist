"""
SQLite-backed storage for the relay.

Three tables:
  users       — registered user UUIDs + their HMAC secrets + opt-in status
  events      — every signed event that arrives, with raw payload + metadata
  audit_log   — append-only log of every relay action (register, submit, review, etc.)

The relay is push-only ingest. The operator pulls events via the /api/v1/events
endpoint with operator auth (a separate, stronger mechanism — see main.py).
"""

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path("/var/lib/hermes-relay/relay.db")


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
    """Create tables if they don't exist. Idempotent."""
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
            FOREIGN KEY (uuid) REFERENCES users(uuid)
        );

        CREATE INDEX IF NOT EXISTS idx_events_uuid ON events(uuid);
        CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

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


# ─── Event operations ──────────────────────────────────────────────────────

def store_event(
    uuid_str: str,
    event_type: str,
    payload: bytes,
    signature_valid: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Store a received event. Returns the event ID."""
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO events (uuid, event_type, received_at, payload, payload_size, signature_valid) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                uuid_str,
                event_type,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                payload,
                len(payload),
                int(signature_valid),
            )
        )
        return cursor.lastrowid


def list_events(
    uuid_str: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    with get_conn(db_path) as conn:
        query = "SELECT id, uuid, event_type, received_at, payload, payload_size, signature_valid FROM events WHERE 1=1"
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
            }
            for r in rows
        ]


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
