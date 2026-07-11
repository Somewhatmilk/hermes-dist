#!/usr/bin/env python3
"""
Recovery probe for a Hermes scratchpad id when the HTTP endpoint
returns empty (pitfall #15 in skill-library-consolidator).

Reads the full plan content directly from the Mnemosyne SQLite
database, since the Mnemosyne MCP tools do NOT search the
`scratchpad` table — only episodic/working memory.

Usage:
    python3 scripts/recover_scratchpad.py <id>
    python3 scripts/recover_scratchpad.py <id> --db <path-to-mnemosyne.db>

Exit codes:
    0 — content recovered (printed to stdout)
    1 — id not found in the scratchpad table
    2 — database file missing or unreadable
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def default_db_path() -> Path:
    hermes_home = os.environ.get("HERMES_HOME")
    base = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    return base / "mnemosyne" / "data" / "mnemosyne.db"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("id", help="scratchpad id (e.g. da151f3644de4eb0)")
    ap.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help="path to mnemosyne.db (default: $HERMES_HOME/mnemosyne/data/mnemosyne.db)",
    )
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: database not found at {args.db}", file=sys.stderr)
        return 2

    try:
        conn = sqlite3.connect(str(args.db))
    except sqlite3.Error as e:
        print(f"ERROR: cannot open {args.db}: {e}", file=sys.stderr)
        return 2

    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT content FROM scratchpad WHERE id = ?", (args.id,)
        ).fetchone()

        if not row:
            ids = [
                r[0]
                for r in cur.execute(
                    "SELECT id FROM scratchpad ORDER BY id LIMIT 50"
                ).fetchall()
            ]
            print(
                f"ERROR: id {args.id!r} not found in scratchpad table. "
                f"Known ids (first 50): {ids}",
                file=sys.stderr,
            )
            return 1

        sys.stdout.write(row[0])
        if not row[0].endswith("\n"):
            sys.stdout.write("\n")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())