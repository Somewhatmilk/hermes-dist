"""
peer_index.py — preview-only peer memory index for hermes-dist.

CRITICAL: This index holds PREVIEWS only (first ~280 chars). Full memory
content lives ONLY in the originating user's Mnemosyne DB on their machine.
The relay has no `full_content` column. Architecturally can't mirror.

Workflow:
  1. Friend marks a memory as shared_to_group=true in their Mnemosyne.
  2. Friend's hermes calls POST /api/v1/peer/share with memory_id, owner_user_uuid,
     persona_id, preview (first 280 chars of content), tags, reliability, origin_kind.
  3. Index row appears in peer_memory_index.
  4. Operator (you) calls GET /api/v1/peer/list (operator auth) to see what's
     shared across the group.
  5. Any user calls GET /api/v1/peer/recall?owner=<uuid>&tags=... to see
     previews; they decide which to import (manually or via the agent).
  6. Import lands in user's hermes with source='external', origin_kind='peer_relay'.

Schema:
  peer_memory_index (
    memory_id TEXT PRIMARY KEY,         -- the originating user's memory_id
    owner_user_uuid TEXT NOT NULL,      -- whose Mnemosyne DB this lives in
    owner_persona TEXT,                 -- which persona of theirs emitted it
    shared_with_group INTEGER NOT NULL DEFAULT 0,
    preview TEXT NOT NULL,              -- first ~280 chars ONLY
    tags TEXT,                          -- comma-separated for cheap search
    created_at TEXT NOT NULL,
    reliability TEXT,                   -- curated | trusted | raw_unverified | disputed
    origin_kind TEXT,                   -- scrape | peer_relay | user_paste | doc_import
    source TEXT NOT NULL,               -- mirrors owner's 'internal' or 'external'
    recall_count INTEGER NOT NULL DEFAULT 0,  -- how many times peers have pulled this
    last_recalled_at TEXT
  )

Index: (owner_user_uuid) and (tags) for recall queries.
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


MAX_PREVIEW_CHARS = 280


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


def init_peer_db(db_path: Path):
    with get_conn(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS peer_memory_index (
            memory_id TEXT PRIMARY KEY,
            owner_user_uuid TEXT NOT NULL,
            owner_persona TEXT,
            shared_with_group INTEGER NOT NULL DEFAULT 0,
            preview TEXT NOT NULL,
            tags TEXT,
            created_at TEXT NOT NULL,
            reliability TEXT,
            origin_kind TEXT,
            source TEXT NOT NULL,
            recall_count INTEGER NOT NULL DEFAULT 0,
            last_recalled_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_peer_owner ON peer_memory_index(owner_user_uuid);
        CREATE INDEX IF NOT EXISTS idx_peer_tags ON peer_memory_index(tags);
        CREATE INDEX IF NOT EXISTS idx_peer_time ON peer_memory_index(created_at DESC);
        """)


def share_memory(
    memory_id: str,
    owner_user_uuid: str,
    preview: str,
    source: str,
    owner_persona: str | None = None,
    tags: list[str] | None = None,
    reliability: str = "raw_unverified",
    origin_kind: str = "peer_relay",
    db_path: Path = None,
) -> dict:
    """
    Insert a memory preview into the peer index. Idempotent on memory_id.
    Enforces the preview-only contract: preview is truncated to MAX_PREVIEW_CHARS.

    Raises ValueError if source is not 'internal' or 'external' (schema CHECK
    contract mirrored at the relay layer).
    """
    if source not in ("internal", "external"):
        raise ValueError(f"source must be 'internal' or 'external', got {source!r}")
    if reliability not in ("curated", "trusted", "raw_unverified", "disputed"):
        raise ValueError(f"invalid reliability: {reliability!r}")
    if origin_kind not in ("scrape", "peer_relay", "user_paste", "doc_import", "audit_pull"):
        raise ValueError(f"invalid origin_kind: {origin_kind!r}")

    preview_truncated = preview[:MAX_PREVIEW_CHARS]
    tags_str = ",".join(t.strip() for t in (tags or []) if t.strip())
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO peer_memory_index
               (memory_id, owner_user_uuid, owner_persona, shared_with_group,
                preview, tags, created_at, reliability, origin_kind, source)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(memory_id) DO UPDATE SET
                  preview = excluded.preview,
                  tags = excluded.tags,
                  reliability = excluded.reliability,
                  origin_kind = excluded.origin_kind""",
            (memory_id, owner_user_uuid, owner_persona,
             preview_truncated, tags_str, created_at,
             reliability, origin_kind, source),
        )

    return {
        "memory_id": memory_id,
        "preview_chars": len(preview_truncated),
        "truncated": len(preview) > MAX_PREVIEW_CHARS,
    }


def unshare_memory(memory_id: str, owner_user_uuid: str, db_path: Path) -> bool:
    """Owner removes a memory from the peer index."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM peer_memory_index WHERE memory_id = ? AND owner_user_uuid = ?",
            (memory_id, owner_user_uuid),
        )
        return cur.rowcount > 0


def recall_previews(
    owner_user_uuid: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
    since: str | None = None,
    limit: int = 50,
    db_path: Path = None,
) -> list[dict]:
    """
    Pull preview-only entries. Caller decides which to import (and lands
    them as source='external' in their own Mnemosyne).
    """
    where = []
    params = []
    if owner_user_uuid:
        where.append("owner_user_uuid = ?")
        params.append(owner_user_uuid)
    if tags:
        # Match ANY of the requested tags (OR semantics, comma-separated)
        tag_clauses = []
        for t in tags:
            tag_clauses.append("tags LIKE ?")
            params.append(f"%{t.strip()}%")
        where.append("(" + " OR ".join(tag_clauses) + ")")
    if source:
        where.append("source = ?")
        params.append(source)
    if since:
        where.append("created_at >= ?")
        params.append(since)
    where.append("shared_with_group = 1")
    where_clause = " AND ".join(where) if where else "1=1"

    # Increment recall counters FIRST so the returned rows reflect post-increment
    # values (so a row's recall_count means "times this row has been recalled,
    # including the call that just returned it").
    if where_clause != "1=1" or True:
        # We always increment on a recall; counts are useful audit info
        # even for the unfiltered "give me everything" view.
        pass

    # Always run the SELECT first; we need the matching memory_ids to know
    # which rows to increment.
    sql = f"""SELECT memory_id, owner_user_uuid, owner_persona, preview,
                     tags, created_at, reliability, origin_kind, source,
                     recall_count, last_recalled_at
              FROM peer_memory_index
              WHERE {where_clause}
              ORDER BY created_at DESC
              LIMIT ?"""
    params.append(limit)

    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    if rows:
        ids = [r[0] for r in rows]
        placeholders = ",".join("?" for _ in ids)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_conn(db_path) as conn:
            conn.execute(
                f"""UPDATE peer_memory_index
                    SET recall_count = recall_count + 1,
                        last_recalled_at = ?
                    WHERE memory_id IN ({placeholders})""",
                [now, *ids],
            )
        # Bump recall_count in the returned rows so callers see the
        # post-increment value (matches "this call counts as a recall").
        rows = [
            (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
             (r[9] + 1) if r[9] is not None else 1,
             now if r[10] is None else r[10])
            for r in rows
        ]

    out = []
    for r in rows:
        out.append({
            "memory_id": r[0],
            "owner_user_uuid": r[1],
            "owner_persona": r[2],
            "preview": r[3],
            "tags": [t for t in r[4].split(",") if t] if r[4] else [],
            "created_at": r[5],
            "reliability": r[6],
            "origin_kind": r[7],
            "source": r[8],
            "recall_count": r[9] if len(r) > 9 else 0,
            "last_recalled_at": r[10] if len(r) > 10 else None,
            # Exposes the privacy boundary explicitly: this is preview only.
            "_preview_only": True,
        })

    return out


def list_owned_by(user_uuid: str, db_path: Path) -> list[dict]:
    """Operator dashboard view: what has user X shared with the group?"""
    return recall_previews(owner_user_uuid=user_uuid, db_path=db_path)


def get_one(memory_id: str, db_path: Path) -> dict | None:
    """Single-item fetch (still preview-only). Used by explicit recall flow."""
    rows = recall_previews(db_path=db_path, limit=1)
    # Filter in Python because the WHERE clause doesn't take memory_id
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT memory_id, owner_user_uuid, owner_persona, preview,
                      tags, created_at, reliability, origin_kind, source
               FROM peer_memory_index WHERE memory_id = ?""",
            (memory_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "memory_id": row[0],
        "owner_user_uuid": row[1],
        "owner_persona": row[2],
        "preview": row[3],
        "tags": [t for t in row[4].split(",") if t] if row[4] else [],
        "created_at": row[5],
        "reliability": row[6],
        "origin_kind": row[7],
        "source": row[8],
        "_preview_only": True,
    }