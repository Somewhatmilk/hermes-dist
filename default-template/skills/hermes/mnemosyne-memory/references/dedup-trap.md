# The 9-vs-237 Dedup Trap

Mnemosyne reported `working: 237 memories, consolidated: 0`. After running `mnemosyne sleep --all-sessions`, only `1` of 237 consolidated. The 236 "stuck" memories were not from old sessions — they were **92.7% duplicates of just 9 unique facts**.

## The dedup signature

237 total memories, fingerprint analysis (first 60 chars) shows ~9 unique groups, 9-22 copies per group. Symptom: recall returns the same top hits on every query ("Session-start ritual" appears in every research / docker / hermes / session query).

## The root cause: write-then-forget anti-pattern

Across sessions, the agent gets reminded of a fact (via toolchain probe, user message, or another recall) and `mnemosyne_remember`s it again instead of just referencing the existing record. The user explicitly called this out: "agent does not retain tool/discovery state across reboots or new sessions."

## The fix (rule, not a tool fix)

### Rule 1 — Recall before remember

**Before any `mnemosyne_remember` call, run `mnemosyne_recall <topic> 5` first.** If the fact is already there with score > 0.80, do NOT re-write. Reference the existing record by ID instead. This single rule cuts the dedup rate by ~90% on the next session.

### Rule 2 — Periodic audit (monthly)

Run a fingerprint pass over mnemosyne:

```bash
# Shell fingerprint pass
for q in $(cat /c/Users/somew/Desktop/Hermes/_test/scripts/mnemosyne_probe_queries.txt); do
  timeout 10 hermes mnemosyne inspect --limit 30 "$q" 2>&1 | grep -oP '^\s*\d+\.\s*\[\d+\.\d+\]\s*\K.{60}'
done | sort | uniq -c | sort -rn | head -20
```

If any fingerprint has count > 5, that's a duplicate cluster. Use `mnemosyne forget <id>` to drop the older copies (keep the most recent or the one with the highest importance score).

For a programmatic fingerprint pass against the SQLite DB directly, see `references/sqlite-direct-inventory.md`.

### Rule 3 — Prefer recall to re-remember

The user's durable facts (session-start ritual, priority order, budget rules) are NOT going to change session-to-session. The cost of an extra `mnemosyne_recall` is sub-millisecond; the cost of duplicate entries is a 5-minute dedup audit.

### Rule 4 — Use targeted invalidation, not bulk delete

For known duplicates, use `mnemosyne_validate --action invalidate` with the `canonical_id` of the original. Idempotent; won't touch unrelated entries. The next `mnemosyne sleep` will then consolidate them.

**Do NOT mass-`mnemosyne forget` to "fix" the dedup.** That loses the unique facts. The right operation is targeted invalidation, not bulk delete.

## The CLI vs agent surface confusion

The hermes CLI for this is `hermes mnemosyne inspect` (NOT `mnemosyne recall` — that's an agent tool name, not a CLI verb). The CLI has: `stats, sleep, version, inspect, clear, doctor, export, import`. The agent has separate tools: `mnemosyne_recall, mnemosyne_remember, mnemosyne_forget, mnemosyne_validate, mnemosyne_sleep, mnemosyne_triple_*`. Conflating them wastes tool calls.

## Cross-references

- `mnemosyne-memory/references/sqlite-direct-inventory.md` — programmatic fingerprint dedup against the SQLite DB directly.
- `mnemosyne-memory/references/recall-discipline.md` — 4-state staleness matrix and the "verify before mutate" protocol.