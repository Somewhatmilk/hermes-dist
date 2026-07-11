"""
mnemosyne-credential-sweep.py
=============================
Re-runnable credential-leak sweep across all mnemosyne text-bearing tables.

Usage:
    python scripts/mnemosyne-credential-sweep.py [db_path]

Default db_path: %LOCALAPPDATA%/hermes/mnemosyne/data/mnemosyne.db

Outputs a plain-text report listing every (table, column, row_id, content_excerpt)
hit per credential pattern. Read the report, decide which rows to DELETE vs REDACT
vs KEEP, then run the targeted cleanup (see SKILL.md "cross-table credential sweep"
pitfall for the decision matrix and the [REDACTED-...] marker convention).

ALWAYS back up mnemosyne.db before running any deletion against it:
    cp mnemosyne.db mnemosyne-pre-sweep-$(date +%s).db

Customize PATTERNS below to add your own known-leaked strings. Public identifiers
(usernames, emails used as contact) should NOT be in PATTERNS — only true secrets.
"""
import sqlite3, os, sys, time

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get('LOCALAPPDATA', r'C:\Users\somew\AppData\Local'),
    'hermes', 'mnemosyne', 'data', 'mnemosyne.db')

# Customize this list for your known-leaked secrets.
# Format: (substring, label) — substring is what LIKE '%X%' matches.
PATTERNS = [
    ('whatisthatmelody',       'reddit-password'),
    ('0987thiciness',          'x-password'),
    ('y2Hz!Nmy_hrb7A',         'discord-password'),
    ('tantehthen673',          'cpanel-password'),
    ('6OMx VPLD VDTC PbS8 AgEQ CnfN',         'wp-app-password'),
    ('WHiDPNZYYvYVI3Qb1FJAyB8MSrFKAxqvP0cJ60hKEbI', 'cpanel-pubkey'),
    ('Milk2043',               'gmail-password'),
    ('hf_lol',                 'hf-token-partial'),
    ('hf_kmv',                 'hf-token-partial-2'),
    ('value lies in the see',  'gpg-passphrase-current'),
    ('all see that views down','gpg-passphrase-old'),
    # Add more here as new leaks surface.
]

TABLES = [
    'working_memory',
    'memories',
    'episodic_memory',
    'consolidated_facts',
    'facts',
    'gists',
    'memoria_facts',
    'memoria_instructions',
    'memoria_preferences',
    'triples',
    'scratchpad',
    'memoria_persona',
]

TEXT_COLS = (
    'content', 'body', 'text', 'summary', 'description',
    'fact', 'subject', 'object', 'predicate'
)


def main():
    if not os.path.exists(DB):
        print(f"ERROR: DB not found at {DB}")
        sys.exit(1)

    print(f"=== MNEMOSYNE CREDENTIAL SWEEP ===")
    print(f"DB:   {DB}")
    print(f"Size: {os.path.getsize(DB):,} bytes")
    print(f"Patterns: {len(PATTERNS)}")
    print(f"Tables: {len(TABLES)}")
    print()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Get row counts for context
    print("Table row counts:")
    for tbl in TABLES:
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {n}")
        except Exception as e:
            print(f"  {tbl}: ERR ({e})")
    print()

    total = 0
    hits_by_table = {}

    for tbl in TABLES:
        try:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({tbl})").fetchall()]
        except Exception:
            continue
        text_cols = [c for c in cols if c in TEXT_COLS]
        if not text_cols:
            continue

        for col in text_cols:
            for substring, label in PATTERNS:
                try:
                    rows = con.execute(
                        f"SELECT id, {col} FROM {tbl} WHERE {col} LIKE ?",
                        (f'%{substring}%',)
                    ).fetchall()
                except Exception:
                    continue
                for r in rows:
                    hits_by_table.setdefault(tbl, 0)
                    hits_by_table[tbl] += 1
                    total += 1
                    excerpt = str(r[1])[:160].replace('\n', ' \\n ')
                    print(f"[{label}] {tbl}.{col} id={r['id'][:16]}")
                    print(f"    {excerpt!r}")

    print()
    print(f"=== SUMMARY: {total} hits across {len(hits_by_table)} tables ===")
    for tbl, n in sorted(hits_by_table.items(), key=lambda x: -x[1]):
        print(f"  {tbl}: {n}")

    if total == 0:
        print("\nCLEAN: no credential patterns found in any mnemosyne table.")
    else:
        print(f"\nNEXT STEPS:")
        print(f"  1. Back up DB: cp \"{DB}\" mnemosyne-pre-cleanup-$(date +%s).db")
        print(f"  2. For each hit above, decide: DELETE / REDACT / KEEP")
        print(f"  3. See SKILL.md 'cross-table credential sweep' for the decision matrix")
        print(f"  4. After deletes, rebuild FTS5: see scripts/rebuild-fts5.py")

    con.close()
    return 0 if total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
