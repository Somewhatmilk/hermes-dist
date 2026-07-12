#!/usr/bin/env python3
"""
prune-orphan-kanban-sessions.py — Remove kanban-dispatched chat sessions
whose task no longer exists in kanban.db.

WHY THIS SCRIPT (not hermes sessions prune):

  hermes sessions prune has filters --source, --cwd, --title, --before,
  --after, etc. We tried them all:
    --cwd %LOCALAPPDATA%\\hermes\\kanban\\boards
      → returns "No sessions match" even for sessions whose cwd is
        verified to start with that path. Looks like a filter bug.
    --source cli
      → matches some sessions but not others; doesn't reliably isolate
        kanban-dispatched sessions
    --before YYYY-MM-DD
      → uses started_at as Unix epoch float; matches a subset based on
        date but doesn't distinguish kanban from non-kanban

  The cleanest way to identify "kanban task sessions whose task is gone"
  is: cwd LIKE '%kanban\\boards%' AND task_id not in kanban.db.

USAGE:
  python3 ~/.hermes/scripts/prune-orphan-kanban-sessions.py --dry-run
  python3 ~/.hermes/scripts/prune-orphan-kanban-sessions.py --yes
"""
import argparse
import os
import sqlite3
import sys
import re
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
PROFILES_DIR = HOME / ".hermes" / "profiles"
KANBAN_DB = HOME / ".hermes" / "kanban.db"
KANBAN_CWD_PREFIX = (
    "C:\\Users\\somew\\AppData\\Local\\hermes\\kanban\\boards"
)


def load_existing_task_ids() -> set[str]:
    """Read all task IDs currently in kanban.db."""
    if not KANBAN_DB.exists():
        return set()
    conn = sqlite3.connect(str(KANBAN_DB))
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks")
    ids = {row[0] for row in cur.fetchall()}
    conn.close()
    return ids


def find_kanban_sessions_in_profile(profile_dir: Path, existing_task_ids: set[str]):
    """Find kanban-dispatched chat sessions in this profile.

    Returns: list of (session_id, task_id, is_orphan)
    """
    state_db = profile_dir / "state.db"
    if not state_db.exists():
        return []
    try:
        conn = sqlite3.connect(str(state_db))
        cur = conn.cursor()
        # Check if 'sessions' table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        if "sessions" not in tables:
            conn.close()
            return []
        cur.execute(
            "SELECT id, cwd FROM sessions WHERE cwd LIKE ?",
            (f"%{KANBAN_CWD_PREFIX}%",)
        )
        results = []
        for sid, cwd in cur.fetchall():
            # Extract task_id from cwd
            m = re.search(r"workspaces[\\/]([^\\/]+)$", cwd or "")
            if m:
                task_id = m.group(1)
                is_orphan = task_id not in existing_task_ids
                results.append((sid, task_id, is_orphan))
        conn.close()
        return results
    except sqlite3.OperationalError as e:
        print(f"  [warn] {profile_dir.name}: {e}")
        return []


def delete_sessions(profile_dir: Path, session_ids: list[str]) -> int:
    """Delete the given sessions from the profile's state.db."""
    if not session_ids:
        return 0
    state_db = profile_dir / "state.db"
    if not state_db.exists():
        return 0
    try:
        conn = sqlite3.connect(str(state_db))
        cur = conn.cursor()
        # Find which tables reference sessions.id
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        # Cascade-delete related rows
        for table in tables:
            if table == "sessions":
                continue
            try:
                cur.execute(f"PRAGMA foreign_key_list({table})")
                fks = cur.fetchall()
                for fk in fks:
                    # fk = (id, seq, table, from, to, on_update, on_delete, match)
                    if fk[2] == "sessions":
                        from_col = fk[3]
                        # Delete related rows
                        placeholders = ",".join("?" * len(session_ids))
                        cur.execute(
                            f"DELETE FROM {table} WHERE {from_col} IN ({placeholders})",
                            session_ids
                        )
            except sqlite3.OperationalError:
                pass
        # Delete the sessions themselves
        placeholders = ",".join("?" * len(session_ids))
        cur.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            session_ids
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return deleted
    except sqlite3.OperationalError as e:
        print(f"  [err] {profile_dir.name}: {e}")
        return 0


def main():
    p = argparse.ArgumentParser(description="Prune orphan kanban-dispatched chat sessions")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be deleted without deleting")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation")
    args = p.parse_args()

    if not args.dry_run and not args.yes:
        print("WARNING: this deletes chat sessions from your state.db.")
        print("Pass --yes to confirm, or --dry-run to preview.")
        sys.exit(1)

    existing = load_existing_task_ids()
    print(f"Tasks in kanban.db: {len(existing)}")

    total_orphan = 0
    total_keep = 0
    by_profile = []

    if not PROFILES_DIR.exists():
        print(f"No profiles dir: {PROFILES_DIR}")
        return

    for pdir in sorted(PROFILES_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        sessions = find_kanban_sessions_in_profile(pdir, existing)
        if not sessions:
            continue
        orphan = [s for s in sessions if s[2]]
        keep = [s for s in sessions if not s[2]]
        total_orphan += len(orphan)
        total_keep += len(keep)
        by_profile.append((pdir.name, orphan, keep))

    print(f"\nKanban sessions across profiles:")
    for name, orphan, keep in by_profile:
        print(f"  {name}: {len(orphan)} orphan, {len(keep)} with live task")

    if args.dry_run:
        print(f"\n[DRY-RUN] Would delete {total_orphan} orphan sessions")
        return

    if not args.yes:
        print("\nPass --yes to actually delete.")
        return

    print(f"\nDeleting {total_orphan} orphan sessions...")
    total_deleted = 0
    for name, orphan, _keep in by_profile:
        if not orphan:
            continue
        sids = [s[0] for s in orphan]
        # Find the profile dir
        pdir = PROFILES_DIR / name
        deleted = delete_sessions(pdir, sids)
        print(f"  {name}: deleted {deleted}")
        total_deleted += deleted

    print(f"\nTotal deleted: {total_deleted}")


if __name__ == "__main__":
    main()