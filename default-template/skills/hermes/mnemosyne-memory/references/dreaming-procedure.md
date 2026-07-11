# Dreaming Cron — 3-Phase Light/Deep/REM Consolidation

**Pattern source:** "Dreaming" by HolmeBengt (r/hermesagent 1udesr1, 328 pts) + **3-phase Light/Deep/REM** by OkSeries5363 (r/hermesagent 1sv06pc, 30 pts). At 3am nightly, an agent reads all conversations from the day, extracts decisions/projects/bugs/people, and writes them to long-term memory. The user wakes up to a smarter agent.

**Why:** Sessions accumulate noise. Without a nightly pass, the agent's recall decays and MEMORY.md bloats past its 2,200-char budget. HolmeBengt's cron is the keystone; OkSeries5363 added the safety rails that make it unattended.

**Honest limitation:** "Long-term memory is still the biggest unsolved problem. Dreaming helps, but session-to-session recall remains inconsistent." This helps — it does not solve.

## The 3 Phases

Each phase has different risk/safety posture.

### Phase 1: LIGHT — read-only scan (autonomous, safe to cron)

- Pull last 24h of sessions via `session_search` (`SELECT * FROM messages WHERE created_at > datetime('now', '-1 day') AND role IN ('user', 'assistant')`)
- Filter trivial turns (greetings, "thanks", empty)
- For each substantive turn, ask the cheap model: "Did this turn produce a stable, retrievable fact? If so, what is it? Also flag any preference changes, corrections, or repeated problems."
- Stage candidates in a dated artifact file (`~/.hermes/skills/mnemosyne-memory/diary/YYYY-MM-DD-light.md`)
- **Does NOT touch MEMORY.md or any wiki** — this phase is read-only

### Phase 2: DEEP — score and promote (autonomous, with safety guard)

For each candidate from Phase 1, score on 4 dimensions:

1. **Novelty** — is this new or already in MEMORY.md? (cheap cosine check via Mnemosyne `recall`)
2. **Durability** — will this still be true in 30 days? (LLM scores 0-1)
3. **Specificity** — is it dense and actionable, not vague? (LLM scores 0-1)
4. **Reduction** — does it reduce other entries to a more general principle? (LLM scores 0-1)

Promotion rules:
- If MEMORY.md is **>60% capacity**, **DEFER all promotions** and emit a "memory lean check recommended" signal to the user's home channel. Do not write.
- If durability × specificity ≥ 0.6, promote to MEMORY.md via `mnemosyne_remember` or to a skill via `mnemosyne_triple_add`
- If novelty is high but durability low, write to the dream diary only (might be ephemeral)
- Log every decision to `diary/YYYY-MM-DD-deep.md` with source session references (the dream diary is append-only for traceability)

### Phase 3: REM — pattern detection (semi-autonomous by default)

- Read the last 3-5 dream diary files
- Use the cheap model to detect recurring patterns:
  - **Repeated corrections** → propose a wiki entry or skill update
  - **Repeated problems** → propose a new skill
  - **Memory gaps** (topics the user keeps re-explaining) → queue for next cycle
- **Default behavior (per OkSeries5363's safety stance):** REM **only reports** patterns to the user's home channel and **waits for approval** before creating wiki pages or skills. Light + Deep are fully autonomous; REM is approval-gated.
- **To make REM fully autonomous:** explicitly opt-in via config flag `dreaming.rem_autonomous: true`. Default is OFF because uncontrolled wiki/skill creation in a cron is dangerous.

## Schedule

- **Dreaming (Light + Deep + REM):** every 12 hours (`0 */12 * * *` — at midnight and noon) — runs unattended
- **Memory lean check:** daily at 3am (`0 3 * * *`) — pair with dreaming
- **Heavy users:** tighten dreaming to every 6 hours (`0 */6 * * *`)

The REM phase can be moved off-cron entirely if you want manual control. The Light+Deep phases are the actual value — REM is a nice-to-have.

## Companion: Memory Lean Check

Dreaming adds entries; lean check trims them. Together they keep MEMORY.md under 60% capacity.

`memory-lean-check` (referenced but separate skill):
- Validates wiki pointers (broken links == wasted bytes)
- Condenses verbose entries (the verbose "user mentioned X" → terse "X")
- Removes stale data (facts the user has explicitly corrected or that contradict newer memories)
- Post-write integrity check so nothing gets corrupted

**When the dreaming pass detects MEMORY.md >60% capacity**, it should invoke memory-lean-check before promoting anything.

## Prerequisites

- Mnemosyne enabled (`mnemosyne_*` tools or `hermes memory setup`)
- Session DB at `~/.hermes/state.db`
- Cheap model available (`auxiliary.background_review.model: google/gemini-3-flash-preview` or `gpt-5-mini`) — extract/score on this, NOT on the main model
- The cron runs in a fresh session — prompt must be **self-contained** with no "today's conversation" ambiguity

## Quick Reference

```bash
# One-shot manual run (debug)
hermes chat -q "/dream"

# Cron schedule (every 12h)
"0 */12 * * *"

# What to write where
mnemosyne_remember(content, importance=0.7)  # facts
mnemosyne_triple_add(subj, pred, obj)        # relationships
mnemosyne_sleep(all_sessions=False)          # optional: trigger consolidation

# Diary location (append-only, for traceability)
~/.hermes/skills/mnemosyne-memory/diary/YYYY-MM-DD-{light,deep,rem}.md
```

## Procedure

1. **Cron triggers** at `0 */12 * * *` (default; configurable)
2. **Phase 1 (LIGHT)** — `session_search` last 24h → cheap model extracts candidates → write to `diary/YYYY-MM-DD-light.md`
3. **Phase 2 (DEEP)** — for each candidate: novelty check via `mnemosyne_recall`, then score 4 dimensions, then promote if score passes AND MEMORY.md is under 60% → log to `diary/YYYY-MM-DD-deep.md`
4. **Phase 3 (REM)** — read last 3-5 diaries → cheap model detects patterns → if `rem_autonomous: true`, create wiki/skill; else report to user's home channel and wait
5. **Capacity check** at end of Phase 2 — if MEMORY.md >60%, emit "lean check recommended" signal
6. **Optional** trigger `mnemosyne_sleep` at end of run to consolidate working memory

## Pitfalls

- **Do NOT skip the capacity check.** A dreaming pass that fills MEMORY.md past 100% will evict the user's important facts. 60% threshold gives the lean check headroom.
- **Do NOT use the main model for extraction or scoring.** The cheap model is enough and 100x cheaper. Main model is for the user's actual task.
- **Do NOT auto-create wiki pages or skills from REM.** OkSeries5363's explicit safety stance: REM reports-and-waits by default. Uncontrolled cron-driven wiki/skill creation has wrecked many setups.
- **Do NOT exceed 50 writes per dreaming cycle** (across all phases combined). Diminishing returns; the 51st fact is rarely worth the storage cost.
- **Do NOT replace the `session-reflection` skill with dreaming.** Session-reflection runs at session end (per-session, fast). Dreaming runs nightly (cross-session, deep). They are complementary.
- **Do NOT run dreaming during a user's active session** — the dream diary and user context will conflict.
- **If using Holographic Memory or Honcho** (not the default MEMORY.md): the dreaming skill can be retuned to write to that backend. The Light/Deep/REM phases still apply; only the promotion target changes.

## Verification

- After 1 week of nightly runs, ask the agent about something discussed 4 days ago. If coherent without restating context, retrieval + binding are working.
- Check `mnemosyne_stats` — episodic count grows, working count stays bounded
- Check MEMORY.md size stays under 60% capacity (1,320 chars if limit is 2,200)
- Monitor the 50-write cap: if hit regularly, tighten the cheap-model filter or the durability threshold
- Spot-check the dream diary: every decision should trace to a specific source session ID

## Cross-references

- `mnemosyne-memory/SKILL.md` — main skill (provider wiring + recall entry points).
- `memory-lean-check` — companion skill, run when dreaming detects MEMORY.md >60%.