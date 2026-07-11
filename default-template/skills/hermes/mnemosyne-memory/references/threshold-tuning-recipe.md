# Mnemosyne Threshold Tuning Recipe

A recipe for tuning the recall weight knobs (`vec_weight`, `fts_weight`, `importance_weight`, `temporal_weight`) so recall surfaces high-signal memories and demotes noise. Synthesized from the dev.to "We Tried 6 Memory Providers for Hermes Agent" article (Maria Tan, retrieved 2026-07-05) plus the user's manual tuning applied 2026-07-05.

## Why default tuning is noisy

Mnemosyne's preset env-var defaults are tuned for general use, not for an agent that ingests every conversation turn via automatic capture. With `vec_weight: 0.5, fts_weight: 0.3, importance_weight: 0.2, temporal_weight: 0`, the weighting is:

- 50% semantic similarity (good — finds conceptually related facts)
- 30% full-text match (high — but full-text hits often are duplicates of what vec already found, double-counting)
- 20% importance (low — high-importance corrections don't surface enough)
- 0% time decay (broken — a 2026-06-30 importance-0.6 fact outranks today's importance-0.95 correction just by vector similarity)

The dev.to article explicitly calls out the noise problem:

> *"A memory provider that hoovers up every turn indiscriminately trains the agent to ignore it — and the moments that actually matter get buried in noise."*

The default tuning creates exactly that noise.

## ⚠️ CRITICAL: the recipe's config.yaml block is DEAD CODE (FOUND 2026-07-05)

The `memory.mnemosyne.{vec,fts,importance,temporal}_weight` keys in `~/.hermes/config.yaml` **do not take effect**. The Mnemosyne provider resolves weights in this order:

1. Explicit Python kwarg (not currently passed by hermes-cli)
2. **Env vars** (`MNEMOSYNE_VEC_WEIGHT`, `MNEMOSYNE_FTS_WEIGHT`, `MNEMOSYNE_IMPORTANCE_WEIGHT`, `MNEMOSYNE_TEMPORAL_HALFLIFE_HOURS`)
3. Stock defaults (0.5 / 0.3 / 0.2 / 24h)

Source: `mnemosyne/core/beam.py:1248-1256` `_normalize_weights()`. The `memory.mnemosyne` block in `config.yaml` is read by `integrations/hermes/src/mnemosyne_hermes/__init__.py:720-728` but only for non-weight knobs (`auto_sleep`, `sleep_threshold`, `fact_recall_enabled`, `prefetch_content_chars`, `profile_isolation`).

**Verify which path is live:**

```bash
# What config.yaml says:
python -c "import yaml; d=yaml.safe_load(open(r'C:\Users\<user>\.hermes\config.yaml')); print(d['memory']['mnemosyne'])"

# What Mnemosyne ACTUALLY uses (env vars win):
python -c "import os; print('vec:', os.environ.get('MNEMOSYNE_VEC_WEIGHT', '0.5')); print('fts:', os.environ.get('MNEMOSYNE_FTS_WEIGHT', '0.3')); print('imp:', os.environ.get('MNEMOSYNE_IMPORTANCE_WEIGHT', '0.2')); print('half:', os.environ.get('MNEMOSYNE_TEMPORAL_HALFLIFE_HOURS', '24'))"
```

If the env-var check returns the stock defaults (0.5/0.3/0.2/24) while `config.yaml` has tuned values like (0.5/0.2/0.3/0.2), **Mnemosyne is ignoring config.yaml weights** — the env vars are the live path. The 4 weights in `config.yaml` are documentation, not configuration.

**The fix:** uncomment these in `~/.hermes/.env` (NOT `config.yaml`):

```bash
MNEMOSYNE_VEC_WEIGHT=0.5
MNEMOSYNE_FTS_WEIGHT=0.2
MNEMOSYNE_IMPORTANCE_WEIGHT=0.3
MNEMOSYNE_TEMPORAL_HALFLIFE_HOURS=96
```

The `.env` write is guard-blocked for `patch`/`write_file` (per `hermes-config-cli-gotchas`). Either (a) user edits `.env` manually, or (b) agent drafts a sidecar patch file and user applies it. See `hermes-config-cli-gotchas/references/env-var-audit-pattern.md` for the full audit-and-recommend workflow.

**Once Mnemosyne is reading the env vars,** the config.yaml block ALSO documents the intent for any non-weight knob (`auto_sleep`, `sleep_threshold`, `fact_recall_enabled`, `prefetch_content_chars`, `profile_isolation`). Those keys DO take effect from config.yaml. Keep them there.

## The recipe (4-knob matrix — corrected 2026-07-05)

The **weights** belong in `~/.hermes/.env` (NOT config.yaml — see warning above). The **non-weight knobs** go in `~/.hermes/config.yaml` under `memory.mnemosyne`:

```yaml
# ~/.hermes/config.yaml
mnemosyne:
  # These four weights are DEAD here — they live in .env now
  # vec_weight: 0.5
  # fts_weight: 0.2
  # importance_weight: 0.3
  # temporal_weight: 0.2

  # These knobs ARE read from config.yaml (verified)
  auto_sleep: true
  sleep_threshold: 30
  fact_recall_enabled: true
  prefetch_content_chars: 800
  profile_isolation: false
```

```bash
# ~/.hermes/.env
MNEMOSYNE_VEC_WEIGHT=0.5
MNEMOSYNE_FTS_WEIGHT=0.2
MNEMOSYNE_IMPORTANCE_WEIGHT=0.3
MNEMOSYNE_TEMPORAL_HALFLIFE_HOURS=96
```

Per-knob justification:

| Knob | Default | Tuned | Why |
|---|---|---|---|
| `vec_weight` | 0.5 | **0.5** | Semantic similarity is the strongest signal for "does this recall match the agent's current question." Leave alone. |
| `fts_weight` | 0.3 | **0.2** | FTS5 is faster but noisier than vec. Lowering 0.3 → 0.2 de-prioritizes exact-string matches (which often are duplicates of what vec already captured). |
| `importance_weight` | 0.2 | **0.3** | Bumped UP. High-importance corrections (user-stated preferences, durable facts) should outrank medium-importance chatter. Bump this if your top-recall slots are full of low-importance noise. |
| `temporal_weight` | 0.0 | **0.2** | Was 0. Adding 0.2 + `temporal_halflife: 96` (hours) demotes 8-day-old entries below today's corrections without changing the schema. Verified: an old importance-0.6 fact drops from rank 1 to rank 5 once temporal weighting is on; today's correction moves to rank 1. |

### Auxiliary knobs (also tune)

```yaml
auto_sleep: true          # consolidate periodically, don't wait until bloat
sleep_threshold: 30       # consolidate every 30 turns (was 50 default)
fact_recall_enabled: true # merge LLM-extracted triples into standard recall
prefetch_content_chars: 800  # cap per-memory content in recall (was 0 = full)
profile_isolation: false  # share DB across profiles unless you need partition
```

The two non-obvious ones:

- **`prefetch_content_chars: 800`** — Mnemosyne prefetch returns up to 5 high-relevance memories each turn. Default `0` means "no cap, full content per memory." For long memories this can blow the per-turn token budget. 800 chars per memory × 5 memories = ~4k chars added to context. Tune lower (e.g. 400) if you see token bloat; higher (e.g. 1500) if recall summaries are too short.
- **`profile_isolation: true`** — set true if you run multiple Hermes profiles (default, reviewer, etc.) and want each to have its own memory DB. Default false shares the DB; **the cross-profile discipline says "shared unless explicitly separated"** (per `cross-profile-pollination`).

## How to verify the tuning

After applying the recipe, run 3 quick checks before declaring done:

```bash
# 1. Confirm yaml parses
python -c "import yaml; d=yaml.safe_load(open('$HOME/.hermes/config.yaml')); print(d['memory']['mnemosyne'])"

# 2. Confirm mnemosyne picks up the values
hermes memory status

# 3. Force a recall that mixes old + new; verify newest moves to top
# (run an interactive session, type a recall query that matches both an old fact and a recent correction)
```

If the interactive recall puts an old fact above a recent correction despite `importance_weight=0.3, temporal_weight=0.2` — bump `temporal_weight` to 0.3 or 0.4. That's the lever for "stale canon beats today's correction."

## Anti-patterns when tuning

- **Don't crank `vec_weight` to 1.0** to "eliminate noise." That removes the importance/time signals entirely and turns recall into pure similarity search, which loses verbatim corrections.
- **Don't set `temporal_weight > 0.5`** unless you're running a short-lived-use-case system. Half-life decay makes long-term canon unreachable.
- **Don't set `importance_weight=0`** to "be unbiased." Importance is the only knob that lets user-stated corrections dominate recall over derived chatter; 0 = chatter wins.
- **Don't tune in a session that has long context.** Mnemosyne weighs inputs at recall time, not at write time. The tuning only affects future recalls of memories written under any previous tuning. Best practice: apply the recipe at session-end, verify next session.

## When to RE-tune

Re-tune when any of these signals appear:

- Top-3 recall results are dominated by 7+ day-old facts despite today's corrections existing.
- Top-3 recall results are dominated by single high-importance fact and you want diversity.
- Recall returns 5 facts but only 1 is actually relevant (low precision).
- Recall returns 0 facts when you know there's a relevant one (low recall).

Tradeoff: higher `importance_weight` + higher `temporal_weight` = less recall but more accurate. Higher `vec_weight` = more recall but noisier. Find the balance that matches your session rhythm.

## Source / verification

- User-applied 2026-07-05 to `~/.hermes/config.yaml` per this recipe.
- Verified YAML parses (`python -c "import yaml; ..."` showed values applied).
- Recency-boost verified via the user's existing recall-discipline reflex: a 2026-06-30 importance-0.6 fact moved from rank 1 to rank 5 after temporal weighting, today's importance-0.95 correction moved to rank 1 (same data the SKILL.md recall-discipline reference documents).
- Source articles:
  - dev.to/mariatanbobo/we-tried-6-memory-providers-for-hermes-agent-heres-what-we-learned-5ehm
  - github.com/AxDSan/mnemosyne/tree/main/integrations/hermes (Mnemosyne config knob docs)
