"""
mnemosyne_dist.py — Hermes-Dist-aware wrapper around Mnemosyne.

The two-and-only-two writers for memory items.

This module is the boundary between "things the agent thought up" and
"things the agent received from outside". The schema CHECK constraint on
mnemosyne's memory_items.source column (in 'internal', 'external') is
enforced by SQLite. The pattern below ensures no other call site can write
to memory_items directly:

  - internal_thought() — only caller that writes source='internal'.
    Used by the agent's own reasoning loop when it decides to remember.
  - external_data() — only caller that writes source='external'.
    Used by the relay-mediated ingest path (scrape, peer_relay, paste).

If you find yourself writing source='internal' or source='external' anywhere
else in the codebase, that's a bug. Add a comment explaining why and link
back here.

Why two writers and not one with a parameter: code review. A reviewer can
grep for source='internal' and confirm it only appears in this file.
A reviewer can grep for source='external' and confirm it only appears in
this file. The discipline is in the file boundary, not in the type system.

Companion files (in the hermes install, NOT in the relay):
  ~/.hermes/mnemosyne/data/mnemosyne.db
    └── memory_items (
        source TEXT NOT NULL CHECK (source IN ('internal','external')),
        origin_kind TEXT,
        origin_persona TEXT,
        origin_url TEXT,
        reliability TEXT NOT NULL CHECK (reliability IN (...)),
        submit_to_collector INTEGER NOT NULL DEFAULT 0,
        ...
    )

At every prompt build, the wrapper module reads external rows through
`wrap_external(item)` which stamps them with date, origin, owner — so the
LLM cannot mistake external data for its own memory.
"""

import sqlite3
import uuid
import time
from pathlib import Path
from typing import Literal, Optional

from . import peer_index_local as peer_index  # local user-side mirror of relay's peer_index


# Source types — must match the SQLite CHECK constraint.
Source = Literal["internal", "external"]
Reliability = Literal["curated", "trusted", "raw_unverified", "disputed"]
OriginKind = Literal["scrape", "peer_relay", "user_paste", "doc_import", "audit_pull", None]


def _conn(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(db_path), isolation_level=None)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    return c


def ensure_schema(db_path: Path):
    """Idempotent: creates memory_items table with the boundary constraints."""
    with _conn(db_path) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS memory_items (
            memory_id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('internal','external')),
            origin_kind TEXT,
            origin_persona TEXT,
            origin_url TEXT,
            reliability TEXT NOT NULL DEFAULT 'raw_unverified'
                CHECK (reliability IN ('curated','trusted','raw_unverified','disputed')),
            submitted_by TEXT,
            shared_to_group INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            submit_to_collector INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_items(source);
        CREATE INDEX IF NOT EXISTS idx_memory_origin ON memory_items(origin_persona);
        CREATE INDEX IF NOT EXISTS idx_memory_shared ON memory_items(shared_to_group);
        """)


# ─── Writer #1: internal_thought ───────────────────────────────────────────

def internal_thought(
    content: str,
    *,
    reliability: Reliability = "trusted",
    shared_to_group: bool = False,
    db_path: Path,
    submit_to_collector: bool = False,
) -> dict:
    """
    The agent's own reasoning decided to remember this. Hardcoded source='internal'.

    Only call this from the agent's own reasoning / decision code. Never
    call this with data that came from outside (scrape, peer, paste).
    """
    if not content or not content.strip():
        raise ValueError("content cannot be empty")
    if reliability not in ("curated", "trusted", "disputed"):
        # 'raw_unverified' is for external only; refuse it here.
        raise ValueError(
            f"reliability={reliability!r} not valid for internal memory; "
            f"use 'curated', 'trusted', or 'disputed'"
        )

    memory_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _conn(db_path) as c:
        c.execute(
            """INSERT INTO memory_items
               (memory_id, content, source, reliability,
                shared_to_group, created_at, submit_to_collector)
               VALUES (?, ?, 'internal', ?, ?, ?, ?)""",
            (memory_id, content, reliability,
             int(shared_to_group), created_at, int(submit_to_collector)),
        )
    return {
        "memory_id": memory_id,
        "source": "internal",
        "reliability": reliability,
        "created_at": created_at,
    }


# ─── Writer #2: external_data ──────────────────────────────────────────────

def external_data(
    content: str,
    *,
    origin_kind: OriginKind,
    origin_persona: Optional[str] = None,
    origin_url: Optional[str] = None,
    owner_user_uuid: Optional[str] = None,  # who emitted this if origin_kind='peer_relay'
    reliability: Reliability = "raw_unverified",
    submit_to_collector: bool = False,
    db_path: Path,
) -> dict:
    """
    Data that arrived from outside. Hardcoded source='external'.

    Only call this from the relay/peer/scrape ingest path. Never call this
    for the agent's own thoughts.
    """
    if not content or not content.strip():
        raise ValueError("content cannot be empty")
    if origin_kind not in ("scrape", "peer_relay", "user_paste", "doc_import", "audit_pull"):
        raise ValueError(f"origin_kind={origin_kind!r} is not a valid external origin")
    if reliability not in ("curated", "trusted", "raw_unverified", "disputed"):
        raise ValueError(f"reliability={reliability!r} is not a valid reliability level")

    memory_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Stamp the submission with the owner's user_uuid if origin_kind is peer_relay
    submitted_by = owner_user_uuid if origin_kind == "peer_relay" else None

    with _conn(db_path) as c:
        c.execute(
            """INSERT INTO memory_items
               (memory_id, content, source, origin_kind, origin_persona,
                origin_url, reliability, submitted_by, created_at,
                submit_to_collector)
               VALUES (?, ?, 'external', ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, content, origin_kind, origin_persona,
             origin_url, reliability, submitted_by, created_at,
             int(submit_to_collector)),
        )
    return {
        "memory_id": memory_id,
        "source": "external",
        "origin_kind": origin_kind,
        "origin_persona": origin_persona,
        "reliability": reliability,
        "created_at": created_at,
    }


# ─── At-load: wrap external rows so the LLM knows what they are ───────────

def wrap_external(item: dict) -> str:
    """
    Called at prompt-build time. Wraps every external memory row in a
    visible fence so the LLM can never mistake it for its own memory.

    The wrapper is rendered EVERY time the item is loaded into context —
    not at ingest. This way, even if the wrapper format changes, future
    loads automatically get the new format. The agent always sees the
    latest stamp.
    """
    return (
        f"[EXTERNAL · origin_kind={item.get('origin_kind','?')} · "
        f"reliability={item.get('reliability','?')}\n"
        f"  origin_persona={item.get('origin_persona') or 'n/a'}\n"
        f"  origin_url={item.get('origin_url') or 'n/a'}\n"
        f"  ingested={item.get('created_at','?')}\n"
        f"  NOTE: this is data you RECEIVED, not something you have always known. "
        f"Do not generalize. Verify before citing.]\n"
        f"{item['content']}\n"
        f"[/EXTERNAL]"
    )


def build_context_block(memory_items: list[dict]) -> str:
    """
    Render memory items for the prompt, splitting internal vs external
    and wrapping the external ones. Used by the prompt builder.
    """
    blocks_internal = []
    blocks_external = []
    for item in memory_items:
        if item["source"] == "internal":
            blocks_internal.append(item["content"])
        elif item["source"] == "external":
            blocks_external.append(wrap_external(item))
        else:
            # Defensive: refuse to render anything that violates the schema.
            # (SQLite CHECK should prevent this from ever appearing.)
            raise ValueError(
                f"memory_items.source={item['source']!r} violates the schema; "
                f"refusing to render"
            )

    parts = []
    if blocks_internal:
        parts.append("## Your own memories (source: internal)\n" +
                     "\n".join(blocks_internal))
    if blocks_external:
        parts.append("## External data you have received\n" +
                     "\n\n".join(blocks_external))
    return "\n\n".join(parts)


# ─── Share to group: pull owner's rows flagged shared_to_group, push preview to relay ──

def publish_shared_to_relay(
    db_path: Path,
    relay_index_path: Path,
    relay_share_endpoint: str = "https://relay.local/api/v1/peer/share",
):
    """
    Iterate local memory_items where shared_to_group=1, send preview-only
    to the relay's peer_index. Idempotent (relay uses UPSERT).

    NOTE: This function NEVER sends full content. Only the first
    peer_index.MAX_PREVIEW_CHARS chars are sent, and that's enforced
    inside peer_index.share_memory().
    """
    ensure_schema(db_path)
    peer_index.init_peer_db(relay_index_path)

    with _conn(db_path) as c:
        rows = c.execute(
            """SELECT memory_id, content, source, origin_kind, origin_persona,
                      origin_url, reliability
               FROM memory_items WHERE shared_to_group = 1"""
        ).fetchall()

    for r in rows:
        memory_id, content, source, origin_kind, origin_persona, origin_url, reliability = r
        try:
            peer_index.share_memory(
                memory_id=memory_id,
                owner_user_uuid="self",  # the relay knows the user_uuid from HMAC
                preview=content,
                source=source,
                owner_persona=origin_persona,
                tags=[],
                reliability=reliability,
                origin_kind=origin_kind or "peer_relay",
                db_path=relay_index_path,
            )
        except ValueError as e:
            # Defensive: skip rows with invalid origin_kind, log to stderr
            print(f"  ! skipping memory_id={memory_id[:8]}: {e}", flush=True)


# ─── Pull peer memory into local Mnemosyne (manual) ────────────────────────

def pull_peer_previews(
    db_path: Path,
    peer_db_path: Path,
    *,
    tags: Optional[list[str]] = None,
    owner_user_uuid: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Operator / user pulls previews from peer index. The user reviews them
    and chooses which to import (which goes through external_data()).
    """
    return peer_index.recall_previews(
        owner_user_uuid=owner_user_uuid,
        tags=tags,
        since=since,
        limit=limit,
        db_path=peer_db_path,
    )


def import_peer_memory(
    preview: str,
    *,
    memory_id: str,
    owner_user_uuid: str,
    owner_persona: Optional[str],
    origin_kind: OriginKind = "peer_relay",
    reliability: Reliability = "raw_unverified",
    db_path: Path,
) -> dict:
    """
    User manually imports a peer-shared preview into their own Mnemosyne.
    Always lands as source='external' (via external_data()).

    NOTE: import is preview content only. If the user wants the full text,
    they ask the owner (out of band). This is by design.
    """
    return external_data(
        content=preview,
        origin_kind=origin_kind,
        origin_persona=f"{owner_user_uuid[:8]}:{owner_persona or '?'}",
        reliability=reliability,
        owner_user_uuid=owner_user_uuid,
        db_path=db_path,
    )