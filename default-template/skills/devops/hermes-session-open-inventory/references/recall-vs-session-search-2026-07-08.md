---
name: recall-vs-session-search
description: 2026-07-08 worked example of the recall-vs-transcript gap. User asked "i asked in a previous session on audit regarding hermes can u recall?" — agent led with mnemosyne_recall, constructed a narrative around a single correction-validated memory note, conflated two different dates (07-06 and 07-08), and quoted the memory as if it were the session transcript. User caught it with "are u not able to review the session or from the logs?" Documents the recovery sequence (no-args session_search browse → find actual session_id → read transcript) and the discriminator rule for "is this an event/utterance or a stable fact?"
type: reference
applies_to: hermes-session-open-inventory
---

# Recall vs. session_search (2026-07-08)

Source session: 2026-07-08, this user. Companion to Pitfall #21 in the umbrella SKILL.md.

## What the user said

> "i asked in a previous session on audit regarding hermes can u recall?"

A recall test. The user wants to know if I can locate and summarize a prior session's work.

## What I did wrong

1. Led with `mnemosyne_recall(query="home audit ~/.hermes review prior session 2026-07", limit=10)`.
2. Got back 10 memory notes. The highest-scored was a `correction-validated` entry from `2026-07-08T16:31:03`:
   > "2026-07-08: failed third time in 14 days on narrow-scope analysis. User asked 'review ~/.hermes' — I checked ONLY `~/.hermes/skills/` and skipped 34 other top-level dirs including the actual project (`hermes-agent-self-evolution/`). Also skipped `~/.hermes/docs/` which has prior `HOME_AUDIT_2026-07-06.md` that would have answered most of it."
3. Constructed my reply around that one memory note. Quoted dates ("Session 2026-07-08, ~16:31"), quoted "the rules I locked in" as if they were verbatim from the session, and conflated the 2026-07-06 audit with the 2026-07-08 attempt.
4. The user caught it within one turn: "are u not able to review the session or from the logs?"

## What I should have done

The user's question is about a specific *event* in a specific past *session*. Mnemosyne is the wrong index. The right first move was:

1. `session_search()` — no-args browse to get the most recent sessions and their titles. This surfaced `session_id: 20260708_165247_178165` ("Full system audit. Do not propose. Execute every safe step.") as a candidate.
2. `session_search(query="Full system audit. Do not propose. Execute every safe step.", sort=newest, limit=3)` — find the actual session.
3. `session_search(session_id="20260708_165247_178165", around_message_id=<last-anchor>)` — scroll the actual transcript.

The actual transcript revealed:
- The session was 7 minutes long (16:52-16:59), 56 messages.
- It produced a **complete Phase 1-3 audit deliverable** (skills tree, profiles, config, root dirs, classification, rewrite plan).
- The final assistant turn said: "I will now execute all safe operations (no config.yaml or SOUL.md changes) and present patches for approval."
- The session then ended — Phase 4 never executed.
- A `phase1-filesystem.json` artifact (60KB) was left in `~/Downloads/audit-2026-07-08/` from an earlier 15:36 attempt.
- The actual session start prompt was: "Full system audit. Do not propose. Execute every safe step." — NOT "review ~/.hermes" as the Mnemosyne memory claimed.

The Mnemosyne memory I cited was a *distilled lesson* about the 07-08 failure, not a *transcript* of the 07-08 session. I treated the lesson as the event.

## Why Mnemosyne led me astray

Mnemosyne ranks by `vec + FTS + importance` (with a `recency_decay` modifier). The memory I cited scored 0.7121 with importance 0.95 — it was a high-importance correction. The FTS query "audit" hit a high-importance note, and the recall returned it as the most relevant match.

The recall API's design is "give me the durable lessons about X." It is NOT "give me the transcript of session Y." Conflating the two is the exact failure mode of Pitfall #18 (stale info as authoritative) extended to memory architecture: Mnemosyne is a *summary* layer, not a *primary source* layer.

## The discriminator rule

When the user asks "do you recall X" / "didn't we do Y" / "what did we do about Z", ask:

> "Is the user asking about an event/utterance/decision in a specific past session, or about a stable fact/preference/convention?"

- **Events** (the audit session, the cron failure, the migration we did) → `session_search` first.
- **Facts** (the user's preferred editor, the always_load config, the Windows path quirks) → `mnemosyne_recall` first.

The English words are the same ("do you recall X"). The content class is different. The user's *intent* is the discriminator, not the words.

## The recovery sequence (worked, this session)

After the user said "are u not able to review the session or from the logs?", I did:

```python
# Step 1: no-args browse for recent sessions
session_search()
# → 3 most recent: 20260707_142430_3d0c3e (Cyber Rules Web Research),
#                   20260708_165247_178165 (no title — the audit),
#                   20260708_133429_f302bf (Multi-task agent fan-out)

# Step 2: read the most likely candidate (preview text matched)
session_search(session_id="20260708_165247_178165")
# → full session read; 56 messages; preview "Full system audit..."

# Step 3: scroll the final assistant turn (the actual deliverable)
# (id 71594 was the audit report; id 71595 was the final tool call.)
```

That gave me the actual Phase 1-3 audit deliverable as a single assistant turn (the message had been delivered in-chat but never written to disk). The Mnemosyne memory I cited first was a *downstream abstraction* of the same session — useful as a "this kind of failure happened" signal, NOT as a substitute for reading the transcript.

## The meta-lesson

Mnemosyne recall is a *summary* of durable lessons. Session transcripts are the *primary source*. When the two diverge (and they will, because memory compresses), the transcript wins. Mnemosyne is the index of *what the agent knows*; session_search is the index of *what was actually said*. Use the right index for the question.

A useful mental model from journalism: Mnemosyne recall is the editor's index card ("on 2026-07-08 we learned X"). session_search is the audio recording of the actual interview. The editor's card is faster to read but lossy; the recording is the ground truth. The user asking "do you recall" is asking whether you have either — and if you have the recording, the card is redundant.

## Cross-references

- Pitfall #21 in `SKILL.md` — the umbrella's stated rule.
- Pitfall #18 (prior-audit TTL) — same class of failure: "X is in memory" ≠ "X is in the session."
- `cross-session-rule-audit` skill — Candidate 2 ("stale info as authoritative") from the 4-cause taxonomy applies: high-importance older memory outranked the live transcript that I should have reached for first.
- `hermes-memory-architecture` skill — the layer model (canonical / triples / scratchpad / shared) is the right framing for understanding *why* Mnemosyne and session_search are different: Mnemosyne compresses, session_search preserves.
