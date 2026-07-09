"""
Manifest storage for the operator's push-update channel.

Operator (via the publish CLI) writes a versioned manifest to this table.
The /api/v1/manifest endpoint reads it; each user gets a personalized slice.

Schema:
  manifest_versions (
    id INTEGER PRIMARY KEY,
    soul_md_version TEXT NOT NULL,         -- monotonic counter, e.g. "v17"
    config_yaml_version TEXT NOT NULL,
    hermes_version TEXT NOT NULL,          -- e.g. "0.4.2" — what version of hermes
                                          --   the operator says the user should run
    soul_md_content TEXT NOT NULL,         -- the actual SOUL.md
    config_yaml_content TEXT NOT NULL,     -- the actual config.yaml
    released_at TEXT NOT NULL,
    released_by TEXT NOT NULL,            -- operator username
    rollout_pct INTEGER NOT NULL DEFAULT 100,  -- for staged rollouts (1..100)
    message TEXT                          -- human-readable release notes
  )

  user_installed_versions (
    user_uuid TEXT PRIMARY KEY,
    soul_md_version TEXT NOT NULL,
    config_yaml_version TEXT NOT NULL,
    last_heartbeat_at TEXT
  )

The user_installed_versions table is updated every time a user polls the
manifest and successfully applies a new version. This is what the operator
sees in the dashboard ("who's running what").
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def get_conn(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_manifest_db(db_path: Path):
    """Create manifest tables. Idempotent. Safe to call from main.py startup."""
    with get_conn(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS manifest_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            soul_md_version TEXT NOT NULL UNIQUE,
            config_yaml_version TEXT NOT NULL,
            hermes_version TEXT NOT NULL,
            soul_md_content TEXT NOT NULL,
            config_yaml_content TEXT NOT NULL,
            released_at TEXT NOT NULL,
            released_by TEXT NOT NULL,
            rollout_pct INTEGER NOT NULL DEFAULT 100,
            message TEXT
        );

        CREATE TABLE IF NOT EXISTS user_installed_versions (
            user_uuid TEXT PRIMARY KEY,
            soul_md_version TEXT,
            config_yaml_version TEXT,
            last_heartbeat_at TEXT,
            FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE
        );
        """)


def publish_manifest(
    soul_md_version: str,
    config_yaml_version: str,
    hermes_version: str,
    soul_md_content: str,
    config_yaml_content: str,
    released_by: str,
    rollout_pct: int = 100,
    message: str = "",
    db_path: Path = None,
) -> int:
    """Operator publishes a new manifest version. Returns the new row id."""
    released_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO manifest_versions
               (soul_md_version, config_yaml_version, hermes_version,
                soul_md_content, config_yaml_content, released_at, released_by,
                rollout_pct, message)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (soul_md_version, config_yaml_version, hermes_version,
             soul_md_content, config_yaml_content, released_at, released_by,
             rollout_pct, message),
        )
        return cur.lastrowid


def get_latest_manifest(db_path: Path) -> dict | None:
    """Return the most recent manifest version, or None."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT soul_md_version, config_yaml_version, hermes_version,
                      soul_md_content, config_yaml_content,
                      released_at, released_by, rollout_pct, message
               FROM manifest_versions
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if not row:
            return None
        return {
            "soul_md_version": row[0],
            "config_yaml_version": row[1],
            "hermes_version": row[2],
            "soul_md_content": row[3],
            "config_yaml_content": row[4],
            "released_at": row[5],
            "released_by": row[6],
            "rollout_pct": row[7],
            "message": row[8],
        }


def get_user_installed(user_uuid: str, db_path: Path) -> dict | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT soul_md_version, config_yaml_version, last_heartbeat_at
               FROM user_installed_versions
               WHERE user_uuid = ?""",
            (user_uuid,),
        ).fetchone()
        if not row:
            return None
        return {
            "soul_md_version": row[0],
            "config_yaml_version": row[1],
            "last_heartbeat_at": row[2],
        }


def record_user_heartbeat(user_uuid: str, soul_md_version: str,
                          config_yaml_version: str, db_path: Path) -> None:
    """Idempotent upsert. Called every heartbeat, with the user's current version."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO user_installed_versions
                  (user_uuid, soul_md_version, config_yaml_version, last_heartbeat_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_uuid) DO UPDATE SET
                  soul_md_version = excluded.soul_md_version,
                  config_yaml_version = excluded.config_yaml_version,
                  last_heartbeat_at = excluded.last_heartbeat_at""",
            (user_uuid, soul_md_version, config_yaml_version, now),
        )


def list_installed_versions(db_path: Path) -> list[dict]:
    """Operator dashboard view: who is running what."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT u.uuid, u.os, u.version AS hermes_installed,
                      iv.soul_md_version, iv.config_yaml_version,
                      iv.last_heartbeat_at
               FROM users u
               LEFT JOIN user_installed_versions iv ON u.uuid = iv.user_uuid
               ORDER BY iv.last_heartbeat_at DESC NULLS LAST"""
        ).fetchall()
    return [
        {
            "user_uuid": r[0],
            "os": r[1],
            "hermes_installed": r[2],
            "soul_md_version": r[3],
            "config_yaml_version": r[4],
            "last_heartbeat_at": r[5],
        }
        for r in rows
    ]
