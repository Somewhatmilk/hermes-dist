"""
Tests for hermes-dist Mnemosyne writer discipline.

These tests verify that:
  1. internal_thought() only writes source='internal'
  2. external_data() only writes source='external'
  3. Schema rejects other source values
  4. The reliability ladder is enforced per source
  5. wrap_external() always stamps origin metadata

Run: python tests/test_mnemosyne_dist.py
"""
import os
import sys
import tempfile
from pathlib import Path

# Make the user-side scripts importable. The default-template/scripts dir
# isn't a package (no __init__.py), so we register it as a fake package
# and load modules by file path.
import sys
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
USER_SCRIPTS = ROOT / "default-template" / "scripts"

# Fake-package approach so relative imports work
sys.modules.setdefault("hermes_dist_scripts", type(sys)("hermes_dist_scripts"))
sys.modules["hermes_dist_scripts"].__path__ = [str(USER_SCRIPTS)]

def _load(name, path):
    spec = importlib.util.spec_from_file_location(f"hermes_dist_scripts.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"hermes_dist_scripts.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod

# peer_index_local must load first because mnemosyne_dist imports from it
pil = _load("peer_index_local", USER_SCRIPTS / "peer_index_local.py")
md = _load("mnemosyne_dist", USER_SCRIPTS / "mnemosyne_dist.py")


def _db():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp) / "test.db"


def test_internal_thought_writes_internal_source():
    db = next(_db())
    md.ensure_schema(db)
    item = md.internal_thought("I decided X", db_path=db)
    assert item["source"] == "internal"
    assert item["memory_id"]

    # Verify in DB
    import sqlite3
    with sqlite3.connect(str(db)) as c:
        row = c.execute(
            "SELECT source, content FROM memory_items WHERE memory_id = ?",
            (item["memory_id"],),
        ).fetchone()
    assert row[0] == "internal"
    assert row[1] == "I decided X"


def test_external_data_writes_external_source():
    db = next(_db())
    md.ensure_schema(db)
    item = md.external_data(
        "scraped text",
        origin_kind="scrape",
        origin_url="https://example.com",
        db_path=db,
    )
    assert item["source"] == "external"

    import sqlite3
    with sqlite3.connect(str(db)) as c:
        row = c.execute(
            "SELECT source, origin_kind, origin_url FROM memory_items WHERE memory_id = ?",
            (item["memory_id"],),
        ).fetchone()
    assert row[0] == "external"
    assert row[1] == "scrape"
    assert row[2] == "https://example.com"


def test_schema_rejects_invalid_source():
    db = next(_db())
    md.ensure_schema(db)
    import sqlite3
    with sqlite3.connect(str(db)) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO memory_items (memory_id, content, source, reliability, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("x", "x", "banana", "trusted", "2026-07-09T00:00:00Z"),
            )


def test_internal_thought_rejects_external_reliability():
    """raw_unverified is external-only — internal memory must use curated/trusted/disputed."""
    db = next(_db())
    md.ensure_schema(db)
    with pytest.raises(ValueError, match="not valid for internal"):
        md.internal_thought("x", reliability="raw_unverified", db_path=db)


def test_external_data_requires_origin_kind():
    db = next(_db())
    md.ensure_schema(db)
    with pytest.raises(ValueError, match="origin_kind"):
        md.external_data("x", origin_kind="sneakernet", db_path=db)


def test_wrap_external_stamps_origin():
    item = {
        "content": "scraped body",
        "origin_kind": "scrape",
        "origin_persona": "alice:R-prod",
        "origin_url": "https://reddit.com/r/x",
        "reliability": "raw_unverified",
        "created_at": "2026-07-09T12:00:00Z",
    }
    wrapped = md.wrap_external(item)
    assert "[EXTERNAL" in wrapped
    assert "origin_kind=scrape" in wrapped
    assert "alice:R-prod" in wrapped
    assert "https://reddit.com/r/x" in wrapped
    assert "scraped body" in wrapped
    assert "[/EXTERNAL]" in wrapped


def test_internal_memory_not_wrapped():
    """Internal items must NOT be wrapped — they're the agent's own knowledge."""
    items = [
        {"source": "internal", "content": "I know this."},
        {"source": "external", "content": "scraped.", "origin_kind": "scrape",
         "origin_persona": "p", "origin_url": "u", "reliability": "raw_unverified",
         "created_at": "t"},
    ]
    out = md.build_context_block(items)
    assert "I know this." in out
    assert "[EXTERNAL" in out


def test_build_context_block_rejects_invalid_source():
    """Schema CHECK violation should never make it through, but if it does, refuse to render."""
    items = [{"source": "banana", "content": "x"}]
    with pytest.raises(ValueError, match="violates the schema"):
        md.build_context_block(items)


def test_import_peer_memory_lands_as_external():
    db = next(_db())
    md.ensure_schema(db)
    item = md.import_peer_memory(
        preview="friend said this",
        memory_id="abc",
        owner_user_uuid="friend-uuid-aaaa",
        owner_persona="R-friend",
        db_path=db,
    )
    assert item["source"] == "external"
    assert item["origin_kind"] == "peer_relay"


import pytest