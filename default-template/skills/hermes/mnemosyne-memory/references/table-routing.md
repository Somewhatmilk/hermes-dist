# Mnemosyne Table Routing

Mnemosyne v3.10 has 5+ tables that look like "memory" but each has a distinct role. The same content goes to different tables depending on what the user wants the agent to DO with it. Defaulting to `canonical_facts` for everything is wrong for ~half the cases.

## The 5+1-table matrix

| Table | What goes here | Example | Update API |
|---|---|---|---|
| `canonical_facts` | Meta-facts ABOUT the user's hermes setup, environment, system state, architecture findings. "This is the state of the system." | "Mnemosyne v3.10.1 at `mnemosyne/data/mnemosyne.db`", "llama-swap on :8089", "Windows 10 + WSL2" | `mnemosyne_remember_canonical(category, name, body)` — overwrite by re-calling with same `(category, name)` |
| `memoria_instructions` | Active behavioral rules the agent must follow. "When user asks X, do Y." | "Use camofox for Reddit", "Lowercase terse voice", "Verify before claiming" | INSERT directly; or `mnemosyne_store` with high importance |
| `memoria_preferences` | Raw user preference facts. "User likes X." | "User prefers lowercase", "User has 6 profiles", "User uses llama-swap" | INSERT directly; or `mnemosyne_store` |
| `memoria_persona` | Persona traits — WHO the user is. v3.10 L3 layer, currently empty for most users. | (typically populated via persona.md auto-promote) | INSERT directly with `tier='long_term'` |
| `episodic_memory` | Per-conversation digests, often large. | Session-end summaries, multi-turn task digests | `mnemosyne_sleep`, auto-generated |
| `scratchpad` | Working/plan notes for the current task. NOT memory. | Skill-library consolidation plans, audit findings, kanban planning scratch | Direct `INSERT` (verify CLI subcommand exists); query directly via SQLite (NOT searchable by `mnemosyne recall`) |

## Decision flow

1. Is it about the SYSTEM (your install, your hermes config, your providers)? → `canonical_facts`
2. Is it a BEHAVIOR RULE the agent must follow? ("when X, do Y") → `memoria_instructions`
3. Is it a USER PREFERENCE or characteristic? ("user likes Y") → `memoria_preferences`
4. Is it a SESSION DIGEST or summary? → `episodic_memory`
5. Is it a PERSONA trait? (e.g. "user is technical, terse, prefers show-don't-tell") → `memoria_persona`
6. Is it a working note for the CURRENT task (plan, scratch, audit output)? → `scratchpad` (NOT a recall target)

## Scratchpad vs memory (don't conflate)

The `scratchpad` table looks like a memory table but it isn't one:

- **`scratchpad`** is task-scoped working space — plans, audits, mid-task scratch. Lifecycle: born in a turn, read in a later turn, abandoned or invalidated when the task ends. Indexed by id (16-char hex like `da151f3644de4eb0`), not by FTS5 query.
- **memory tables** (`canonical_facts`, `memoria_instructions`, `memoria_preferences`, `memoria_persona`, `episodic_memory`) are user-scoped durable state — facts/rules/preferences the agent should know across sessions.

Two operational differences that bite (verified 2026-07-04):

1. **`mnemosyne recall "<topic>"` does NOT search `scratchpad`.** If a user cites a scratchpad id like `da151f3644de4eb0`, query SQLite directly:
   ```bash
   sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db \
     "SELECT id, substr(content,1,200) FROM scratchpad WHERE id LIKE '%<hex>%' OR content LIKE '%<keyword>%';"
   ```
2. **Don't store scratchpad content as a memory fact.** A consolidation plan is not a behavioral rule. If you `mnemosyne remember` the plan, the agent will treat it as a live instruction. Keep scratchpad scratchpad.

## The common mistake (defaulting to canonical_facts)

Behavioral rules ("use camofox for Reddit", "verify before claiming", "lettered menu for multi-step options") are NOT system meta-facts — they're instructions. They belong in `memoria_instructions`, not `canonical_facts`. The user-profile draft text was 4 instructions, not 4 canonical facts.

Routing them correctly is the difference between:
- **Agent follows the rule** (instructions table, treated as live behavior)
- **Agent sees the rule as historical context and ignores it** (canonical_facts table, treated as state)

## `memoria_instructions` schema

```sql
CREATE TABLE memoria_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT DEFAULT 'default',
    message_idx INTEGER,
    instruction TEXT,
    active INTEGER DEFAULT 1,
    topic TEXT,
    context_snippet TEXT,
    source_memory_id TEXT
);
```

`active=1` is the live filter. To soft-disable an instruction, set `active=0`. To hard-remove, `DELETE WHERE topic=<name>`. Source memory IDs are optional provenance pointers.

## The two-subsystem ID confusion (canonical vs working)

There are two memory subsystems in Mnemosyne with different ID schemes and different update APIs:

| Subsystem | ID type | Update API |
|---|---|---|
| Working / episodic memories (FTS5-indexed) | 16-char hex string | `mnemosyne_update(memory_id="<16-char hex>")` works |
| Canonical slots (keyed by `(category, name)`) | Integer ID returned by `mnemosyne_remember_canonical` (e.g. `{"id": 1}`) | `mnemosyne_update(memory_id=1)` returns `{"status": "not_found"}` — use `mnemosyne_remember_canonical` again with same `(category, name)` to overwrite |

**Symptom when you hit it:** `mnemosyne_update(memory_id=1)` silently returns `not_found`. The canonical record is unchanged. No error, no warning.

**Why it happens:** the canonical subsystem uses `(category, name)` as the natural key and tracks integer IDs internally for FTS5 indexing. The update tool's lookup path checks the 16-char hex working-memory table first, doesn't find the integer, returns `not_found`.

**The right pattern:**

1. Create a canonical: `mnemosyne_remember_canonical(category="host-environment", name="tool-stack", body="...")`. Response includes `"id": 1`.
2. To update: call `mnemosyne_remember_canonical(category="host-environment", name="tool-stack", body="<new body>")` again with the same name. It overwrites the slot, increments the version, updates `valid_from`. The integer ID stays the same.
3. To verify: `mnemosyne_recall_canonical(category="host-environment")` shows the new body, the bumped version, and new `valid_from`.

**Don't try to "fix" the integer ID issue** by passing strings like `mnemosyne_update(memory_id="host-environment/tool-stack")` — that also returns `not_found`. The two subsystems are separate.

## Cross-references

- `mnemosyne-memory/SKILL.md` — main skill, slim overview.
- `mnemosyne-memory/references/recall-discipline.md` — when to trust recalled facts and how to mutate them.
- `mnemosyne-memory/references/sqlite-direct-inventory.md` — direct DB access for the underlying tables.