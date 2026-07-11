"""
rebuild-fts5.py
===============
Rebuild the three FTS5 indexes that back mnemosyne's recall path.

When to run this:
  - After any DELETE against working_memory, episodic_memory, or consolidated_facts
  - When mnemosyne_recall returns "database disk image is malformed"
  - When mnemosyne_recall returns stale results (matches deleted rows)
  - After restoring a backup of mnemosyne.db

Usage:
    python scripts/rebuild-fts5.py [db_path]
"""
import sqlite3, os, sys

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get('LOCALAPPDATA', r'C:\Users\somew\AppData\Local'),
    'hermes', 'mnemosyne', 'data', 'mnemosyne.db')


def main():
    if not os.path.exists(DB):
        print(f"ERROR: DB not found at {DB}")
        sys.exit(1)

    con = sqlite3.connect(DB)
    print(f"DB: {DB}")

    targets = [
        ('fts_working',   'working_memory'),
        ('fts_episodes',  'episodic_memory'),
        ('fts_facts',     'consolidated_facts'),
    ]

    for fts_name, src_table in targets:
        try:
            before = con.execute(f"SELECT COUNT(*) FROM {fts_name}").fetchone()[0]
            con.execute(f"INSERT INTO {fts_name}({fts_name}) VALUES('rebuild')")
            con.commit()
            after = con.execute(f"SELECT COUNT(*) FROM {fts_name}").fetchone()[0]
            try:
                src_count = con.execute(f"SELECT COUNT(*) FROM {src_table}").fetchone()[0]
            except Exception:
                src_count = '?'
            print(f"  {fts_name}: rebuilt OK ({before} -> {after} rows, source {src_table} has {src_count})")
        except Exception as e:
            print(f"  {fts_name}: ERROR — {e}")

    con.close()


if __name__ == '__main__':
    main()
