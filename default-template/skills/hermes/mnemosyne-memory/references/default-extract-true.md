# Default `extract=True` on durable `mnemosyne_remember`

## The rule (one line)

Every durable `mnemosyne_remember` call passes `extract=True, extract_entities=True` unless the content falls into one of the three exceptions below.

## Why this rule exists

Verified live on 2026-07-13 by direct sqlite read of `~/.hermes/mnemosyne/data/mnemosyne.db`:

| Table | Rows | Role |
|---|---|---|
| `memoria_kg` | 61 | Real SPO triple store. Indexed on `subject` + `predicate`. Schema `(id, session_id, subject, predicate, object, message_idx, confidence, source_memory_id)`. |
| `graph_edges` | 1689 | All `edge_type='ctx'`. Auto-populated by `mnemosyne_remember` lifecycle. Structure `gist_<id>` → `fact_<id>_<n>`. |
| `triples` | 9 | Vestigial / older schema. Empty in normal use. |

The wrapper exposes all four relational tools (`mnemosyne_triple_add`, `mnemosyne_triple_query`, `mnemosyne_graph_link`, `mnemosyne_graph_query`) and the `extract=True` / `extract_entities=True` parameters on `mnemosyne_remember`. The sleep cycle reads `extract=True` writes and promotes their decomposition into `memoria_kg`. **Across this profile's entire history, the default invocation has been `mnemosyne_remember(content=...)` with no extract parameter set**, so the relational graph has stayed at 61 triples despite dozens of durable remembers.

This rule is the State 2 encoding of habit memory id `942264022c4aaa98`. A memory entry alone is State 1 (advisory) — the agent can ignore it. A SKILL.md pitfall is State 2 (operational) — the agent sees it at session-start index time and is expected to follow it.

## When `extract=True` is correct (the default)

Any fact where all three of subject, predicate, and object are individually stable and queryable. Examples:

- "BrightData is_a residential_proxy" → triple candidate
- "BrightData anonymity_grade F" → triple candidate
- "Mullvad pricing €5/mo flat, no account" → triple candidate
- "Whonix is_a vm_based_os" → triple candidate
- "kanban dispatcher lives_in hermes_gateway" → triple candidate
- "rule: default extract=True on durable remember" → triple candidate (the rule itself becomes queryable)

For every `mnemosyne_remember(content=<structured fact>)` call → add `extract=True, extract_entities=True`.

## Three exceptions where `extract=False` is correct

### 1. Ephemeral working notes
Use `mnemosyne_scratchpad_write` instead of `mnemosyne_remember`. Scratchpad is session-scoped, NOT in recall ranking, and exists exactly for short-lived notes that should not pollute the persistent graph. Adding `extract=True` to a scratchpad write is doubly wrong — wrong tool, wrong extraction.

### 2. Narrative paragraphs where prose is the unit of value
Some content depends on its narrative structure to carry meaning. Decomposing it into SPO triples fragments the context.

Examples that should NOT be `extract=True`:
- Session-end handoff documents (`"## Today's decisions: 1. ... 2. ... 3. ..."`)
- Design notes with embedded reasoning (`"The reason we picked X over Y is ... because ..."`)
- Process documentation that walks through steps
- Diagnostic narratives explaining a debugging session
- User-voice reflections on preferences

These are paragraphs by intent. Write them as paragraphs. They live in `mnemosyne_recall` via vector+fts but do not participate in the relational graph. That's correct.

### 3. Bulk import of existing prose
If importing a previously-written document, re-extraction can create duplicate triples that already exist in `memoria_kg` from earlier `extract=True` writes of the same content. Verify with `mnemosyne_triple_query(subject=<key terms>)` before importing. If duplicates would result, write to `mnemosyne_scratchpad_write` (ephemeral) or skip the import entirely.

## Threshold rule (when in doubt)

Ask: **does the fact have a stable subject, a stable predicate, and a stable object, all three individually queryable?**

- All three yes → `extract=True` (the default)
- Any one is ambiguous or context-dependent → `extract=False` (write the paragraph)
- The content is a paragraph by intent → `extract=False` regardless

## Companion read-side habit (still to encode)

When the user asks "what do I know about X" or references a prior topic:

1. **First**, call `mnemosyne_triple_query(subject=X)` and `mnemosyne_triple_query(object=X)` to surface structured facts.
2. **Then**, call `mnemosyne_graph_query(seed=<id>, max_hops=2)` if you have a seed memory id, to expand the cluster.
3. **Only then**, fall back to `mnemosyne_recall(query=X)` for vector+fts ranked snippets.

Without the read-side habit, the write-side data has no consumer. The graph fills itself but no one reads from it. This is the next State 2 rule to encode (proposed tic: "user asks 'what do I know about X' → STOP, fire triple_query + graph_query before recall").

## Verification recipe

After a session that produced several `mnemosyne_remember(extract=True)` calls:

```bash
# 1. live counts (should grow over time)
sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db \
  "SELECT
     (SELECT COUNT(*) FROM memoria_kg)      AS kg_triples,
     (SELECT COUNT(*) FROM graph_edges
      WHERE edge_type != 'ctx')              AS non_ctx_edges,
     (SELECT COUNT(*) FROM triples)          AS legacy_triples,
     (SELECT COUNT(*) FROM memories
      WHERE metadata_json LIKE '%extract%'
         OR content LIKE '%extract%True%')    AS extract_tagged;"

# 2. sample triples from the last hour (should reflect the writes you made)
sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db \
  "SELECT subject, predicate, substr(object,1,80), confidence
   FROM memoria_kg
   ORDER BY id DESC LIMIT 20;"

# 3. if memoria_kg is still empty after a session with many remembers,
#    the extract=True flag was not honored — likely a code path or
#    env var override (check MNEMOSYNE_EXTRACT_DEFAULT).
```

If `kg_triples` is non-zero and growing session-over-session, the rule is holding. If it stays flat, re-read the pitfall — the default invocation is still missing the parameter.

## Common failure modes (from this profile's history)

- **Habit didn't load this session** — symptom: agent says "I'll write a quick remember" without the parameters. Check: top-of-prompt `<memory-context>` block carries the habit rule id? If not, the skill wasn't loaded.
- **Sleep cycle isn't running** — symptom: extracts happened (memoria_kg rows appear) but recall doesn't surface them. Verify with `mnemosyne_stats` that `working.unconsolidated` is shrinking and `episodic.total` is growing. If `unconsolidated` keeps growing, the cron isn't firing — see "Default consolidation LLM is broken" pitfall (same file, Pitfalls index, "Consolidation" section).
- **Concurrency collision on `extract=True`** — symptom: rare. Mnemosyne dedupes by `(subject, predicate, object)` hash. Two parallel remembers with identical SPO triples merge into one row. No data loss, just one fewer row than expected.
- **The content was actually a paragraph** — symptom: `extract=True` produced 0 or low-quality triples, content still readable in vector+fts. Re-classify as Exception #2 above; no further action needed.

## Cross-references

- `mnemosyne-memory/SKILL.md` Pitfalls section, "Default `extract=True` on every durable `mnemosyne_remember`" — the load-bearing rule entry
- `mnemosyne-memory/references/library-vs-wrapper-surface-2026-07-07.md` — verification recipe for `mnemosyne_*` tool existence before citing
- `mnemosyne-memory/references/recall-discipline.md` — read-side discipline (use temporal_weight, dedup before remember)
- `mnemosyne-memory/references/dedup-trap.md` — "before any `mnemosyne_remember`, run `mnemosyne_recall` first" — pairs with extract=True to prevent duplicate triple writes
- `hermes-skill-loading-disciplines/references/agent-self-tics.md` — the tic row added 2026-07-13 that fires this rule at write time
- Habit memory id `942264022c4aaa98` (importance 0.95, source=fact) — the State 1 version of this rule
- Companion memory id `1c06feff77062837` — verified live graph state 2026-07-13 (memoria_kg=61, graph_edges=1689, triples=9)

## Origin

Habit rule raised in conversation 2026-07-13 after direct sqlite read disproved the agent's claim that "the knowledge graph is empty." The truth: the graph IS populated (61 triples + 1689 context edges) but is sparsely populated relative to the number of remember calls. The gap is write discipline, not infrastructure. Encoded as State 2 pitfall here so the next session's loader surfaces it at index time.