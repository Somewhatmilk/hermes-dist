---
name: mnemosyne-tuning
description: "Mnemosyne recall-weight and consolidation-tuning recommendations for parallel-session workflows. The current defaults are tuned for general use and can drop high-importance recent content in favor of mid-importance older content. Use this skill when: recall seems to be returning irrelevant or stale memories; you just had a context-window consolidation and lost important detail; you're running parallel sessions and the cross-session handoff feels lossy. The fix is per-call weight tuning + writing high-importance facts with a future valid_until — NOT a single global config change."
version: 1.1.0
author: Hermes Agent (default profile, derived from consolidation-failure-mode observation 2026-07-12; v1.1.0 corrected 2026-07-12 after grep-verifying what Mnemosyne actually accepts)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [mnemosyne, tuning, memory, recall, consolidation, parallel-sessions]
    category: hermes
    related_skills: [mnemosyne-memory, mnemosyne-curator, cross-session-todo-handoff, failures-journal]
    config: []
---

# Mnemosyne Tuning for Parallel-Session Workflows

> **Use this skill when:** Mnemosyne recall feels lossy, stale, or
> dominated by mid-importance noise. Specifically:
> - You just had a context-window consolidation and lost important detail
> - You're running parallel sessions and the cross-session handoff feels lossy
> - Recall returns 5 mid-importance facts from old sessions when you want 1-2 high-importance recent facts
> - You write a `mnemosyne_remember(importance=0.85, valid_until=...)` and it's not surfacing
>
> **Do NOT use this skill when:** the recall is fine and you're just looking for a specific fact (use `mnemosyne_recall` directly with a specific query).

## The problem (observed 2026-07-12)

The agent shipped a v0.4.2 commit at importance 0.85 + valid_until 2026-09-12. In a later session, the `<memory-context>` block surfaced 5 mid-importance (0.60) facts from old sessions and **not the v0.4.2 detail**. Two things were wrong:

1. **The hybrid recall weights** (env: `MNEMOSYNE_VEC_WEIGHT`, `MNEMOSYNE_FTS_WEIGHT`, `MNEMOSYNE_IMPORTANCE_WEIGHT`) default to (0.5, 0.3, 0.2). With a 0.2 importance weight, even a 0.85-importance fact doesn't dominate the ranking.
2. **The temporal halflife** is 96 hours (4 days). For a 2-week-old fact that's still load-bearing, it under-ranks.

Combined: the algorithm prefers "mid-importance + recent" over "high-importance + slightly older."

## What Mnemosyne actually accepts (v1.1.0 correction)

I checked the actual source code (`~/.hermes/hermes-agent/venv/Lib/site-packages/mnemosyne/core/beam.py`) and the plugin (`~/.hermes/plugins/mnemosyne/__init__.py`). Here's what works and what doesn't:

### What works (per-call, in `mnemosyne_recall`)

```python
mnemosyne_recall(
    query="<q>",
    limit=10,                          # top_k
    vec_weight=0.4,                    # passed-through to beam.recall
    fts_weight=0.3,                    # passed-through to beam.recall
    importance_weight=0.3,             # passed-through to beam.recall
    temporal_weight=0.5,               # bias toward recent
    temporal_halflife=96,              # hours
    query_time="<ISO timestamp>",      # for time-relative queries
)
```

The plugin's `__init__.py` line 1085-1095 explicitly forwards `vec_weight`, `fts_weight`, `importance_weight` to `beam.recall()`. The env vars (`MNEMOSYNE_*_WEIGHT`) are the fallback when not passed per-call.

### What works (env var, persistent)

```bash
export MNEMOSYNE_VEC_WEIGHT=0.4
export MNEMOSYNE_FTS_WEIGHT=0.3
export MNEMOSYNE_IMPORTANCE_WEIGHT=0.3
export MNEMOSYNE_TEMPORAL_HALFLIFE_HOURS=96
```

These are read by `beam._normalize_weights()` and `beam.recall()` when no per-call override is given.

### What works (config file, persistent)

`~/.hermes/config.yaml` under `memory.mnemosyne.*` — keys that are read by the plugin include:
- `auto_sleep: bool` (default: true)
- `sleep_threshold: int` (default: 30)
- `profile_isolation: bool` (default: true)
- `shared_surface_path: str` (default: `data/shared/mnemosyne.db`)

The recall weights are **not** in the config file schema — they're env-var-or-per-call only.

### What does NOT work (yet)

- `recall_weights: {vec, fts, importance}` in `~/.hermes/config.yaml` — **not in the schema**. The plugin only reads the env vars or per-call args. Putting it in config.yaml has no effect.
- `preserve_above_importance: 0.75` in config — **not in the schema**.
- `preserve_with_valid_until: true` in config — **not in the schema**.

These were MY speculation in v1.0.0 of this skill. **They are wrong.** The v1.1.0 update corrects this.

### What DOES work for "do not consolidate"

The `working_memory` table has a `pinned` column. `sleep()` filters with:
```sql
AND (pinned IS NULL OR pinned = 0)
```

So **`pinned=1` items survive consolidation and stay in working memory.** But the `mnemosyne_remember` wrapper tool does NOT expose a `pinned` parameter — you'd have to set it via raw SQL or modify the plugin. The high-importance + valid_until combination is the practical workaround (sleep() preserves high-importance items because they rank above the consolidation threshold).

## The fix (concrete, verified)

### 1. Per-call weight tuning in your session-start ritual

When you run `mnemosyne_recall` at session start, pass the tuned weights:

```python
mnemosyne_recall(
    query="open work in-progress hermes-dist",
    limit=5,
    vec_weight=0.4,        # was 0.5
    fts_weight=0.3,        # unchanged
    importance_weight=0.3, # was 0.2 — BUMP
    temporal_weight=0.5,   # bias recent
    temporal_halflife=96,  # 4 days
)
```

### 2. Persistent env-var override (if you want this for all sessions)

Add to `~/.hermes/.env` or your shell init:
```bash
export MNEMOSYNE_VEC_WEIGHT=0.4
export MNEMOSYNE_FTS_WEIGHT=0.3
export MNEMOSYNE_IMPORTANCE_WEIGHT=0.3
```

### 3. The handoff-write pattern (always)

When you write a handoff note, **always** combine:
- High importance (≥0.85)
- `valid_until` set ~1 month out
- A canonical slot write (`mnemosyne_remember_canonical`)

The canonical slot supersedes recall entirely; the high-importance remember ranks above the consolidation threshold; the valid_until makes the consolidation algorithm's "freshness" decision favor it.

## How to verify the tuning worked

1. **Write a probe memory** with importance 0.85, valid_until 1 month out:
   ```python
   mnemosyne_remember(
       content="TUNING-PROBE: if you see this, recall_weights=0.4/0.3/0.3 work",
       importance=0.85,
       valid_until="<+30 days>",
       source="mnemosyne-tuning-probe"
   )
   ```

2. **In a fresh session**, ask an adjacent question and look for the probe in `<memory-context>`. If it surfaces, the tuning is working.

3. **Delete the probe** with `mnemosyne_invalidate` or `mnemosyne_forget` once verified.

## When NOT to tune

- **Your recall is fine.** Don't tune what isn't broken.
- **You want to find old facts.** Tuning for high-importance-recency makes old facts harder to find.
- **You have < 1000 memories.** Tuning matters more at 10k+.

## The complementary pattern: cross-session-todo-handoff

Recall tuning is **necessary but not sufficient**. The cross-session-todo-handoff skill (separate, opt-in) provides a structured handoff ritual that survives any consolidation algorithm by writing to a canonical slot. The two patterns work together:

- **Recall tuning** makes high-importance recent facts surface more reliably
- **Cross-session-todo-handoff** writes state that doesn't depend on recall ranking at all (canonical slots supersede recall)

For parallel-session workflows, do both.

## Worked example (v0.4.2 case)

**Before tuning:**
- v0.4.2 detail (importance 0.85, valid_until 2026-09-12) was dropped from `<memory-context>` in favor of 5 mid-importance (0.60) old facts

**After applying the recommended per-call weights + handoff-write pattern:**
- v0.4.2 detail (importance 0.85) ranks higher in the top-N
- The canonical slot `work.in_progress` holds the structured form, independent of recall
- `valid_until=2026-09-12` keeps the dated handoff above the freshness cutoff

**Verifying:** write a probe, ask an adjacent question in a fresh session, look for the probe in `<memory-context>`.

## Related

- `mnemosyne-memory` — full Mnemosyne API surface
- `mnemosyne-curator` — memory hygiene + sleep cycle
- `cross-session-todo-handoff` — structured handoff pattern (complements this)
- `failures-journal` — error patterns + recovery (this is a "failure-pattern" skill in the same family)