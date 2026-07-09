"""
Tests for hermes-dist peer index (preview-only enforcement).

The peer index holds 280-char previews only. These tests verify:
  1. share_memory truncates to MAX_PREVIEW_CHARS
  2. source validation rejects non-internal/non-external
  3. reliability validation
  4. origin_kind validation
  5. unshare_memory only removes the owner's row
  6. recall_previews increments the recall_count

Run: python -m pytest tests/test_peer_index.py -v
or:   python tests/test_peer_index.py
"""
import os
import sys
import tempfile
from pathlib import Path

# Make the relay module importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from relay.app import peer_index


@pytest.fixture
def peer_db():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "peer.db"
        peer_index.init_peer_db(db)
        yield db


def test_share_truncates_to_max_preview(peer_db):
    long_text = "x" * 1000
    result = peer_index.share_memory(
        memory_id="m1",
        owner_user_uuid="user-aaaa",
        preview=long_text,
        source="internal",
        db_path=peer_db,
    )
    assert result["truncated"] is True
    assert result["preview_chars"] == peer_index.MAX_PREVIEW_CHARS

    # Read back and verify truncation
    items = peer_index.recall_previews(db_path=peer_db)
    assert len(items) == 1
    assert len(items[0]["preview"]) == peer_index.MAX_PREVIEW_CHARS


def test_share_rejects_invalid_source(peer_db):
    with pytest.raises(ValueError, match="source must be"):
        peer_index.share_memory(
            memory_id="m1",
            owner_user_uuid="u",
            preview="hello",
            source="banana",
            db_path=peer_db,
        )


def test_share_rejects_invalid_reliability(peer_db):
    with pytest.raises(ValueError, match="invalid reliability"):
        peer_index.share_memory(
            memory_id="m1",
            owner_user_uuid="u",
            preview="hi",
            source="external",
            reliability="very_unreliable",
            db_path=peer_db,
        )


def test_share_rejects_invalid_origin_kind(peer_db):
    with pytest.raises(ValueError, match="invalid origin_kind"):
        peer_index.share_memory(
            memory_id="m1",
            owner_user_uuid="u",
            preview="hi",
            source="external",
            origin_kind="sneakernet",
            db_path=peer_db,
        )


def test_unshare_only_owner(peer_db):
    peer_index.share_memory(memory_id="m1", owner_user_uuid="alice",
                            preview="alice thought", source="internal", db_path=peer_db)
    peer_index.share_memory(memory_id="m2", owner_user_uuid="bob",
                            preview="bob thought", source="internal", db_path=peer_db)

    # Alice tries to unshare bob's memory — should fail (return False)
    assert peer_index.unshare_memory("m2", "alice", peer_db) is False
    # Bob unshares his own — should succeed
    assert peer_index.unshare_memory("m2", "bob", peer_db) is True

    items = peer_index.recall_previews(db_path=peer_db)
    assert len(items) == 1
    assert items[0]["memory_id"] == "m1"


def test_recall_increments_counter(peer_db):
    peer_index.share_memory(memory_id="m1", owner_user_uuid="alice",
                            preview="hi", source="internal", db_path=peer_db)
    peer_index.recall_previews(db_path=peer_db)
    peer_index.recall_previews(db_path=peer_db)

    items = peer_index.recall_previews(db_path=peer_db)
    assert items[0]["recall_count"] == 3


def test_recall_filters_by_owner(peer_db):
    peer_index.share_memory(memory_id="m1", owner_user_uuid="alice",
                            preview="alice-1", source="internal", db_path=peer_db)
    peer_index.share_memory(memory_id="m2", owner_user_uuid="bob",
                            preview="bob-1", source="internal", db_path=peer_db)

    alice_only = peer_index.recall_previews(owner_user_uuid="alice", db_path=peer_db)
    assert len(alice_only) == 1
    assert alice_only[0]["memory_id"] == "m1"


def test_recall_filters_by_source(peer_db):
    peer_index.share_memory(memory_id="m1", owner_user_uuid="u",
                            preview="int", source="internal", db_path=peer_db)
    peer_index.share_memory(memory_id="m2", owner_user_uuid="u",
                            preview="ext", source="external", db_path=peer_db)

    internal_only = peer_index.recall_previews(source="internal", db_path=peer_db)
    assert len(internal_only) == 1
    assert internal_only[0]["memory_id"] == "m1"


def test_no_full_content_in_index():
    """The peer index module must not have a `full_content` column anywhere."""
    import inspect
    import re
    src = inspect.getsource(peer_index)
    # Strip docstrings (they legitimately describe what we DON'T store)
    src_no_docstrings = re.sub(r'"""[\s\S]*?"""', '', src)
    src_no_docstrings = re.sub(r"'''[\s\S]*?'''", '', src_no_docstrings)

    # Look for actual SQL/storage usage: column declarations, INSERT/SELECT
    # columns, or assignment to a variable named full_content.
    patterns = [
        r'full_content\s*=',                    # Python assignment
        r'full_content\s+TEXT',                 # SQL column declaration
        r'full_content\s+BLOB',                 # SQL column declaration
        r'INSERT.*INTO.*full_content',          # SQL INSERT mentioning it
        r'SELECT.*full_content',                # SQL SELECT mentioning it
    ]
    for pat in patterns:
        match = re.search(pat, src_no_docstrings, re.IGNORECASE)
        assert not match, \
            f"peer_index.py references full_content (matched: {match.group()!r}); privacy boundary violated"

    # Also: there's no method named with full_content
    method_names = [name for name in dir(peer_index) if not name.startswith("_")]
    assert not any("full_content" in n for n in method_names), \
        f"peer_index exposes a full_content method: {method_names}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))