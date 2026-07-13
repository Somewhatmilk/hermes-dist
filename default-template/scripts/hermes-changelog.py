#!/usr/bin/env python3
"""
hermes-changelog.py — Cross-session change-log tool.

Writes a timestamped markdown entry to:
  1. ~/Desktop/Obsidian Vault/Cross-Session/changes/<ISO>-<slug>.md
     (human-browsable audit log)
  2. ~/.hermes/mnemosyne/data/shared/mnemosyne.db via mnemosyne_shared_remember
     (cross-session recall)

Usage:
  python3 hermes-changelog.py --kind skill-shipped --slug cross-session-todo-handoff \\
      --summary "New opt-in skill for cross-session todo continuity" \\
      --details "Wrote handoff.read and handoff.write rituals..."

  python3 hermes-changelog.py --kind architecture-shift --slug shared-surface-read \\
      --summary "Enabled shared_surface_read: true in mnemosyne config" \\
      --details "Now recall merges shared-surface results from other sessions"

  python3 hermes-changelog.py --list  # show last 20 changes
"""
from __future__ import annotations
import argparse, os, sys, json, re
from pathlib import Path
from datetime import datetime, timezone

VAULT = Path(os.environ.get("OBSIDIAN_VAULT") or
             (Path.home() / "Desktop" / "Obsidian Vault"))
CHANGES_DIR = VAULT / "Cross-Session" / "changes"
MNEMOSYNE_SHARED_DB = (Path.home() / ".hermes" / "mnemosyne" / "data"
                       / "shared" / "mnemosyne.db")


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", s.strip().lower())
    return re.sub(r"-+", "-", s).strip("-")[:60]


def write_obsidian(slug: str, kind: str, summary: str,
                   details: str, source: str = "hermes-changelog") -> Path:
    """Write a markdown file under Obsidian/changes/."""
    CHANGES_DIR.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    fname = f"{iso}-{slug}.md"
    path = CHANGES_DIR / fname
    body = f"""---
kind: {kind}
slug: {slug}
source: {source}
timestamp: {iso}
---

# {summary}

**Kind:** {kind}
**Slug:** `{slug}`
**UTC:** {iso}

## Details

{details}

---
*Logged by hermes-changelog.py. View all changes:*
`Cross-Session/changes/*.md`
"""
    path.write_text(body, encoding="utf-8")
    return path


def write_mnemosyne_shared(slug: str, kind: str, summary: str,
                            details: str, source: str = "hermes-changelog") -> str | None:
    """Write to Mnemosyne shared surface via the wrapper tool if available."""
    try:
        # Use the Mnemosyne wrapper via its plugin (when run inside hermes context)
        # Fall back to direct DB INSERT if plugin unavailable
        import importlib.util
        candidates = [
            Path.home() / ".hermes" / "plugins" / "mnemosyne" / "__init__.py",
            Path.home() / ".hermes" / "plugins" / "mnemosyne" / "tools.py",
            Path.home() / ".hermes-agent" / "plugins" / "mnemosyne" / "__init__.py",
        ]
        for cand in candidates:
            if cand.exists():
                spec = importlib.util.spec_from_file_location("mnemosyne_plugin", str(cand))
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(mod)
                except Exception:
                    continue
                # Try the high-level wrapper first
                if hasattr(mod, "mnemosyne_shared_remember"):
                    return mod.mnemosyne_shared_remember(
                        content=f"[{kind}/{slug}] {summary}\n\n{details}",
                        importance=0.8,
                        source=source,
                        veracity="stated",
                    )
        # Fall back: direct DB INSERT to shared surface
        return _direct_db_insert(slug, kind, summary, details, source)
    except Exception as e:
        sys.stderr.write(f"[warn] mnemosyne write failed: {e}\n")
    return None


def _direct_db_insert(slug: str, kind: str, summary: str, details: str,
                       source: str = "hermes-changelog") -> str | None:
    """Direct SQLite INSERT into the Mnemosyne shared surface DB."""
    try:
        import sqlite3
        import uuid
        from datetime import datetime, timezone
        if not MNEMOSYNE_SHARED_DB.exists():
            return None
        conn = sqlite3.connect(str(MNEMOSYNE_SHARED_DB))
        cur = conn.cursor()
        # Mnemosyne working_memory schema (per grep-verified)
        memory_id = uuid.uuid4().hex[:16]
        now_iso = datetime.now(timezone.utc).isoformat()
        content = f"[{kind}/{slug}] {summary}\n\n{details}"
        # Try the schema, fall back gracefully
        try:
            cur.execute("""
                INSERT INTO working_memory
                    (id, content, source, timestamp, importance,
                     metadata_json, scope, valid_until, veracity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (memory_id, content, source, now_iso, 0.8,
                  json.dumps({"kind": kind, "slug": slug, "obsidian": True}),
                  "global", None, "stated"))
            conn.commit()
            return memory_id
        except sqlite3.OperationalError as e:
            sys.stderr.write(f"[warn] shared DB schema mismatch: {e}\n")
            return None
        finally:
            conn.close()
    except Exception as e:
        sys.stderr.write(f"[warn] direct DB insert failed: {e}\n")
        return None


def list_changes(limit: int = 20) -> list[dict]:
    """List most recent change files."""
    if not CHANGES_DIR.exists():
        return []
    files = sorted(CHANGES_DIR.glob("*.md"), key=lambda p: p.name, reverse=True)
    out = []
    for f in files[:limit]:
        out.append({
            "file": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        })
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description="Cross-session change-log writer for Hermes + Obsidian",
    )
    p.add_argument("--kind", choices=["skill-shipped", "skill-modified",
                                       "architecture-shift", "config-change",
                                       "memory-update", "tool-installed",
                                       "bug-fix", "other"],
                   help="What kind of change is being logged")
    p.add_argument("--slug", help="Kebab-case identifier for this change")
    p.add_argument("--summary", help="One-line summary of the change")
    p.add_argument("--details", help="Multi-line details / reasoning")
    p.add_argument("--source", default="hermes-changelog",
                   help="Origin tool / agent / session")
    p.add_argument("--list", action="store_true",
                   help="List recent changes (read-only)")
    p.add_argument("--limit", type=int, default=20,
                   help="Limit for --list (default 20)")
    p.add_argument("--no-mnemosyne", action="store_true",
                   help="Skip Mnemosyne shared-surface write (Obsidian only)")
    args = p.parse_args()

    if args.list:
        items = list_changes(args.limit)
        if not items:
            print(f"No changes yet in {CHANGES_DIR}")
            return 0
        print(f"Recent changes in {CHANGES_DIR}:")
        print()
        for it in items:
            print(f"  {it['file']}  ({it['size']} bytes, {it['modified']})")
        return 0

    if not (args.kind and args.slug and args.summary):
        p.error("--kind, --slug, and --summary are required (or use --list)")

    slug = slugify(args.slug)
    path = write_obsidian(slug, args.kind, args.summary,
                           args.details or "", args.source)
    print(f"[obsidian] wrote {path}")

    if not args.no_mnemosyne:
        mem_id = write_mnemosyne_shared(slug, args.kind, args.summary,
                                         args.details or "", args.source)
        if mem_id:
            print(f"[mnemosyne] wrote shared-surface memory {mem_id}")
        else:
            print(f"[mnemosyne] skipped (wrapper unavailable)")

    print()
    print(f"Logged: [{args.kind}] {args.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())