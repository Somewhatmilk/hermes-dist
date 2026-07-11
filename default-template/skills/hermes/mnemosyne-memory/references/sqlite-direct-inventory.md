# SQLite-direct Mnemosyne inventory

## When the CLI isn't enough

`hermes mnemosyne inspect` only returns content snippets with vector-search scores. It does NOT give you:

- the `id` (UUID) of a specific memory
- the row count in the underlying tables
- a way to list ALL memories (inspect is query-driven, so you only see what matches your probe)
- a way to find duplicates by content fingerprint
- the schema (tables, columns, indexes)

For those, you read the SQLite DB directly. The DB is one file, no auth, no lock issues for read-only access.

## The DB path and key tables

```
~/.hermes/mnemosyne/data/mnemosyne.db
```

(Windows: `C:\Users\<user>\AppData\Local\hermes\mnemosyne\data\mnemosyne.db`)

Tables you'll care about (verified Jun 2026, mnemosyne 3.10+):

| Table | Purpose | Row count signal |
|---|---|---|
| `working_memory` | Hot context, auto-injected before LLM calls. **Auto-logged conversation entries live here** | The "bloat" the user sees in the agent's context |
| `episodic_memory` | Long-term with sqlite-vec + FTS5 hybrid search. **Consolidated facts live here** | What `mnemosyne sleep` should grow |
| `memories` | The "raw remember" tier (less used by Hermes plugin; mostly raw mnemosyne SDK calls) | Mid-tier; cross-check vs working_memory |
| `memoria_facts` | Extracted structured facts (`key` / `value` / `context_snippet` columns) | The 176 facts from `mnemosyne stats` output |
| `memoria_instructions` | Behavioral instructions derived from conversations | 36 typically |
| `memoria_preferences` | User preference extractions | 12 typically |
| `consolidation_log` | Audit trail of `mnemosyne sleep` runs | Small; check after consolidation |
| `scratchpad` | **Working / plan notes for the current task — NOT in FTS5.** When the user cites a short hex id (e.g. `da151f3644de4eb0`) it is almost certainly a `scratchpad` row. Query this table directly via sqlite3, do not waste a `mnemosyne recall` call. See schema block below. | Spikes during multi-step plans; cleared on session close |
| `vec_working` / `vec_episodes` / `vec_facts` | sqlite-vec virtual tables for the embedding vectors | Vectors, not inspectable as text |
| `fts_working` / `fts_episodes` / `fts_facts` | FTS5 full-text indexes | Mirror the corresponding memory tables |

The hybrid scoring (50% vec + 30% FTS + 20% importance) is computed at recall time against these tables, not stored as a "score" column.

## Read-only inventory (no hermes restart needed)

```python
import sqlite3, os
db = os.path.expanduser(r'~\AppData\Local\hermes\mnemosyne\data\mnemosyne.db')
conn = sqlite3.connect(db)
cur = conn.cursor()

# Row counts
for t in ('working_memory', 'episodic_memory', 'memories',
         'memoria_facts', 'memoria_instructions', 'memoria_preferences',
         'consolidation_log'):
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'{t:<25} {cur.fetchone()[0]} rows')
```

## Schemas that don't have a `content` column (FOUND 2026-07-04 reviewing a scratchpad plan)

The mnemonic "Mnemosyne = SQL with `content` everywhere" is wrong. Three tables you'll hit while debugging follow `(key, value, …)` or `(id, content, …)` patterns, and a fourth (`scratchpad`) has `content` but is in NO FTS index. Verified schemas (mnemosyne 3.10):

```sql
-- memoria_facts: extracted structured facts
-- columns: id, session_id, message_idx, fact_type, key, value,
--          context_snippet, importance, timestamp, version_id,
--          previous_value, updated_msg_idx, valid_from_msg_idx,
--          valid_to_msg_idx, source_memory_id
-- Find a fact by keyword:
SELECT key, substr(value,1,200), importance, timestamp
FROM memoria_facts
WHERE value LIKE '%<keyword>%' OR key LIKE '%<keyword>%'
ORDER BY timestamp DESC LIMIT 10;

-- memoria_instructions: behavioral rules
-- columns: id, session_id, message_idx, key, instruction_text,
--          importance, timestamp, version_id, source_memory_id
-- NB: the instruction lives in `instruction_text`, not `content` or `value`.
SELECT key, substr(instruction_text,1,200), importance
FROM memoria_instructions
ORDER BY importance DESC LIMIT 10;

-- scratchpad: working / plan notes (NOT in any FTS index)
-- columns: id, content, session_id, created_at, updated_at
-- Default recall tools return nothing for scratchpad rows.
-- If the user cites a short hex id, this is where it lives:
SELECT id, substr(content,1,300), created_at
FROM scratchpad
WHERE id LIKE '%<hex_prefix>%'
   OR content LIKE '%<keyword>%'
ORDER BY updated_at DESC;

-- memories: the raw remember tier
-- columns: id, content, source, timestamp, session_id, importance,
--          metadata_json, created_at
-- This one DOES have `content` — fingerprints and dedup work normally here.
```

**Default rule:** before any `SELECT content FROM <mnemosyne_table>` blast, run `PRAGMA table_info(<table>)` first. Three of the most-queried tables (`memoria_facts`, `memoria_instructions`, `memoria_persona`) store the payload in non-`content` columns. A `SELECT content` against those returns `OperationalError: no such column: content` and burns a tool call.

## Find duplicates by content fingerprint

The "9 unique facts out of 237 memories" finding came from fingerprinting on the first 60 chars of the `content` column. Code:

```python
from collections import defaultdict
import sqlite3

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT id, content, importance, timestamp FROM working_memory ORDER BY timestamp DESC')
rows = cur.fetchall()

groups = defaultdict(list)
for id_, content, importance, timestamp in rows:
    groups[content[:60]].append({
        'id': id_, 'importance': importance, 'timestamp': timestamp
    })

# Identify the "keep" per group (highest importance, then most recent)
to_delete = []
for fp, members in groups.items():
    if len(members) > 1:
        keep = max(members, key=lambda m: (m['importance'], m['timestamp']))
        for m in members:
            if m['id'] != keep['id']:
                to_delete.append(m['id'])

print(f'unique fingerprints: {len(groups)}, total rows: {len(rows)}, would delete: {len(to_delete)}')
```

**Reality check from Jun 2026 session:** on this host, `working_memory` had 243 rows but 241 unique fingerprints. The "92% redundant" finding from the inspect-driven probe was wrong because the inspect tool was returning near-duplicates by vector similarity, not by content match. The actual dedup opportunity was tiny (2 rows). **Don't trust a probe-based dedup estimate without cross-checking via the direct DB path.**

## Delete or invalidate

Two options, both valid:

```python
# Option A: HARD delete (cleaner, loses history)
cur.execute(f'DELETE FROM working_memory WHERE id = ?', (id_,))

# Option B: SOFT invalidate (keeps row, marks superseded via memory_validations)
# Per the Mnemosyne docs, mnemosyne_invalidate writes a row to memory_validations
# with action='invalidate'. The recall code filters these out at query time.
# Safer if you want to audit the deletions later.
```

Hard delete is fine for working_memory (auto-logged, can be regenerated). For `episodic_memory` (consolidated facts that took an LLM call to produce), prefer invalidate.

## When to run this

- When `mnemosyne stats` shows working_memory exploding (>1000) and you want to see the actual breakdown
- Before any mass-delete: ALWAYS verify the fingerprint distribution first
- When debugging "the agent keeps saying X even though I corrected it" — check if there's a high-importance memory overriding the more recent correction
- For audit: what memories are auto-injected before each LLM call

## Safety notes

- `~/.hermes/mnemosyne/data/mnemosyne.db` is read-safe. The hermes gateway holds a write lock during mnemosyne operations, but reads from a separate sqlite3 connection always succeed.
- DO NOT write to this DB while hermes is actively calling `mnemosyne_recall` or `mnemosyne_remember` from another connection. Either pause the hermes gateway (`hermes gateway stop`) or stick to read operations.
- Backup the DB before any mass delete: `cp mnemosyne.db mnemosyne.db.pre-dedup-<ts>`. If something goes wrong, restore from the backup. The hermes-state-backup.sh cron backs up `mnemosyne-export/memories.json` (the export), not the raw DB — different artifact, different recovery.
- The hermes CLI's `mnemosyne clear` exists and wipes everything. Use the direct-DB approach if you want surgical deletes, not the nuke option.

## Related

- The mnemosyne 3.10+ architecture (BEAM: bilevel episodic-associative memory, working + episodic + TripleStore) is documented in the github README, not in this reference. Read the upstream README for the "why" behind the two-tier design; this reference is the "how to inspect" complement.
- `session` step 1 — the live-state probe, before diving into memory.
- `references/mnemosyne-rag-injection.md` in `session` — the in-body `<memory-context>` block, unrelated to the SQLite layer.
