# Mnemosyne Credential Sweep Recipe

When you suspect a credential has been pasted in chat and may have ended up in mnemosyne, `mnemosyne_recall <token>` is **NOT sufficient**. Recall only searches `fts_working`. Mnemosyne has at least 6 text-bearing tables where credentials can hide, and a leak sweep MUST touch all of them.

## The 6+ tables

| Table | What's in it | How it can leak |
|---|---|---|
| `working_memory` | The prefetch target — typically the largest table | Most common landing zone. Most leaks here. |
| `memories` | Older core memories (subset of working_memory) | Some records exist in both. Sweep both. |
| `episodic_memory` | Per-conversation digests, often huge | One digest can hold every credential pasted in a whole conversation |
| `consolidated_facts` | Subject-predicate-object triples from sleep runs | Username-only facts get consolidated even if the password row was deleted |
| `gists` | Short text snippets, often USER/ASSISTANT raw turns | Harder to search; pattern-match on credential-shaped strings, not full recall |
| `facts` / `memoria_*` | Other derived/sleep outputs | Lower-yield but worth checking |

## The sweep recipe

Customize the `PATTERNS` list with the substrings you suspect have leaked, then run:

```python
import sqlite3
DB = r'C:\Users\<user>\AppData\Local\hermes\mnemosyne\data\mnemosyne.db'
con = sqlite3.connect(DB)

PATTERNS = [
    # add the substrings you suspect have leaked; do NOT include full
    # credentials here even when sweeping — partial-substring match is enough
    'your-substring-1', 'your-substring-2',
]
TABLES = ['working_memory', 'memories', 'episodic_memory',
          'consolidated_facts', 'facts', 'gists']

for tbl in TABLES:
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({tbl})").fetchall()]
    text_cols = [c for c in cols if c in
                 ('content', 'body', 'text', 'subject', 'object', 'predicate')]
    for col in text_cols:
        for sec in PATTERNS:
            for row in con.execute(
                f"SELECT id, {col} FROM {tbl} WHERE {col} LIKE ?",
                (f'%{sec}%',)).fetchall():
                print(f"  {tbl}.{col} {row[0]}: {str(row[1])[:120]!r}")
```

Or use the re-runnable script: `scripts/mnemosyne-credential-sweep.py`. ~5s for a 12MB DB.

## Decision matrix after the sweep

| What you find | Action |
|---|---|
| Plaintext password dump (entire mem IS the credential) | **DELETE** the row. Low structural value, high risk. |
| High-importance mem with credential AS PART OF useful context (imp ≥ 0.85, structure matters) | **REDACT in place.** Replace literal with `[REDACTED-<TYPE>-LEAKED-<DATE>]`. Bump importance to mark as audit-completed. |
| Gist or episodic digest that summarizes a whole conversation containing leaked creds | **DELETE** the digest. The conversation is in `state.db`; the digest is just a leak surface. |
| Username-only mention (e.g. a public Reddit handle) | **KEEP.** Public identifiers aren't credentials. Don't false-positive redact these. |
| Old passphrases that have been rotated | **REDACT** with `[REDACTED-OLD-<TYPE>-ROTATED-<DATE>]`. Keep the structural fact (e.g. "vault uses AES256 GPG") but drop the literal value. |
| Email address as a contact, not a credential | **KEEP.** Same logic as username. |

## The `[REDACTED-...]` marker convention

When you redact in place, the marker MUST encode:
- **(a)** what was redacted
- **(b)** when it was found
- **(c)** that it's known-leaked

Pattern: `[REDACTED-<WHAT>-LEAKED-YYYY-MM-DD]`. Example: `[REDACTED-GPG-PASSPHRASE-2026-06-25]`. Future recall of this row surfaces the redacted string, which signals "this is the audited-safe version" rather than looking like an unrelated token.

## Critical gotcha: row IDs are 16-char hex, not 12-char prefixes

Mnemosyne's `mnemosyne_forget` CLI accepts the full ID. Using the 12-char prefix in a SQL `WHERE id = ?` clause silently misses the row and the DELETE is a no-op. Always use the full 16-char string.

## After any DELETE, rebuild FTS5

So the search index reflects the new state:

```python
con.execute("INSERT INTO fts_working(fts_working) VALUES('rebuild')")
con.execute("INSERT INTO fts_episodes(fts_episodes) VALUES('rebuild')")
con.execute("INSERT INTO fts_facts(fts_facts) VALUES('rebuild')")
con.commit()
```

Or use `scripts/rebuild-fts5.py`. If you skip this, `mnemosyne_recall` may still return the deleted content because the FTS5 rowid→content mapping is stale.

## Always back up the DB BEFORE the sweep

```bash
cp mnemosyne.db mnemosyne-pre-sweep-<timestamp>.db
```

The sweep can break FTS5 (empty stream / malformed errors); the rebuild fixes it but you want the option to rollback if you deleted something you shouldn't have.

## Then tell the user to rotate the leaked credentials

Encryption-at-rest doesn't help if the plaintext was already in a session log that may have been synced upstream. See `security` for the rotation workflow.