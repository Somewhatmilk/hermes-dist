---
name: cross-session-todo-handoff
description: "Cross-session todo continuity for parallel-session workflows. Reads/writes the `work.in_progress` canonical Mnemosyne slot to bridge session boundaries. Use at session START to discover open work from prior sessions; use at session END or PIVOT to write a handoff note (high importance, valid_until date) so the next session finds it. Triggers on: fresh session with parallel-session context, user asks 'what's pending' or 'what did we do last time', agent reaches a natural break point, agent transitions between unrelated work streams."
version: 1.0.0
author: Hermes Agent (default profile, derived from session-continuity patterns 2026-07-12)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [meta, session-continuity, mnemosyne, handoff, todo, parallel-sessions]
    category: meta
    related_skills: [session, mnemosyne-memory, mnemosyne-curator, hermes-session-open-inventory, routing]
    config: []
---

# Cross-Session Todo Handoff

> **Use this skill when:** you run multiple parallel sessions with
> different queries, and you want the next session to know what
> the previous one was working on. The problem this solves:
> "I asked the agent about X yesterday, today I'm asking about Y
> in a fresh session, and the agent doesn't know X is half-done."
>
> **Do NOT use this skill when:** you're in a single-session linear
> workflow (no parallel sessions), or you don't care about
> cross-session continuity.

## The problem (one paragraph)

Mnemosyne handles recall well for *facts* (a value at a point in
time), but it doesn't have a first-class "open work" concept. Open
work is **stateful + open-ended + has a not-yet-done-ness to it**.
Facts say "X is true." Open work says "X is being worked on, and
the current state is Y." A new session can recall facts, but it
has no signal that something is IN-PROGRESS unless the agent
explicitly writes a high-importance dated note.

## The fix (one paragraph)

Use a **canonical Mnemosyne slot** as the source-of-truth for
"what's in progress" + a **session ritual** that reads it on
session start and writes it on session end. The slot name is
`work.in_progress` (canonical, supersedes cleanly). The session
ritual is two thin commands: `cross-session-todo.handoff.read`
and `cross-session-todo.handoff.write`.

## The two rituals

### 1. Session start: `handoff.read`

Run as one of your first moves in a fresh session, especially if
you suspect prior work is pending:

```python
# Use the mnemosyne_recall_canonical tool
mnemosyne_recall_canonical(category="work", name="in_progress")
# Returns the current value of ~/.hermes/mnemosyne/canonical/work/in_progress
# Format: a single free-text body with the current open items, dated,
# with status, and a "do not consolidate" hint (high importance).
```

If the slot returns empty, **first session** — no prior handoff.
If the slot returns text, **read it before answering any user
query**. Ask yourself: "is the user's current question related to
any of the open items? If yes, resume. If no, note that the new
work is being added and the open items stay open."

You can also do a temporal-weighted recall to catch open items
that are not yet in the canonical slot but were noted as
`mnemosyne_remember` calls with high importance + valid_until:

```python
mnemosyne_recall(
    query="open work in-progress hermes-dist",
    limit=5,
    temporal_weight=0.5,   # bias toward recent + still-valid
)
```

### 2. Session end / pivot: `handoff.write`

When you finish a work item, pivot to a new one, or reach a
natural break point, write a handoff note. This is the part most
agents (and humans) forget, which is why the failure mode exists.

```python
# Step 1: Update the canonical slot
mnemosyne_remember_canonical(
    category="work",
    name="in_progress",
    body="""
Current open work (as of YYYY-MM-DD):

1. <item name> — <one-line status>
   - Last touched: YYYY-MM-DD
   - Blocked by / waiting on: <if any>
   - Estimated effort: <hours or days>
   - Decision: <what was decided last session>

2. <item name> — <one-line status>
   ...

Closed since last handoff:
- <item> (closed YYYY-MM-DD, commit <sha> if relevant)
"""
)

# Step 2: Also write a high-importance mnemosyne_remember so
# sleep() consolidation doesn't lose the in-progress signal
mnemosyne_remember(
    content="<one-paragraph summary of current state, what's pending,
             and what was decided>",
    importance=0.85,
    veracity="stated",
    valid_until="<date 1 month out>",
    source="<project or skill name>"
)
```

The canonical slot is the **structured, queryable** form. The
`mnemosyne_remember` call is the **durable, recall-ranked** form.
Both are written, so the next session finds it whether it reads
the canonical slot OR does a recall.

## Worked example (the hermes-dist v0.4.1 case)

**Symptom:** User runs parallel sessions. In one, we ship
v0.4.1-skills. In another fresh session tomorrow, user asks
"let's continue hermes-dist work." Agent doesn't know about
the v0.4.2 Linux/macOS installer parity TODO because no
handoff was written.

**Without this skill:** agent re-discovers the gap by reading
git log, but doesn't know what was *decided* (defer-to-v0.4.2)
or *why* (user chose Windows-first during v0.4.0 design).

**With this skill (handoff.write at end of v0.4.1 session):**

```python
mnemosyne_remember_canonical(
    category="work", name="in_progress",
    body="""
Open work: hermes-dist v0.4.2 — Linux/macOS installer parity.
State as of 2026-07-12: v0.4.1-skills shipped (commit 0dd8581).
DEFERRED: install-linux.sh and install-macos.sh at v0.3.0; need
v0.4.0/v0.4.1 parity (notify-send on Linux, osascript on macOS).
Why: user explicitly chose Windows-first during v0.4.0 design.
Estimated effort: ~2 hours total.

Closed: 6 new opt-in skills, mnemosyne-memory Mental Model section,
config.yaml + SHIP.md update. Commits 0dd8581 + tag v0.4.1-skills.
"""
)
```

**In the next session:**
```python
mnemosyne_recall_canonical(category="work", name="in_progress")
# Returns the body above. Agent reads it before answering the user's
# new query, sees the open work, and either resumes or asks the
# user "do you want to do v0.4.2 (Linux/macOS) now?"
```

## When to use each form

| Use canonical slot | Use mnemosyne_remember |
|---|---|
| Source-of-truth, always-current state | Recall-ranked, durable across many sessions |
| Single body, supersedes cleanly | Multiple entries, importance-ranked |
| Read with `recall_canonical` | Read with `recall` + temporal_weight |
| Best for: "what's in progress RIGHT NOW" | Best for: "what do I know about X that should still matter" |

**Write BOTH** for important open work. The canonical slot is the
"phone book" entry; the remember is the "notes" entry.

## The 5 anti-patterns

### 1. "I'll write the handoff at the end of the project"
You won't. The project changes, the session ends, and the handoff
never gets written. **Write the handoff at every natural break
point**, not just at "the end."

### 2. "I'll just remember the open work mentally"
You are a fresh agent in a new session. You have no mental
continuity across sessions. **The handoff is the only thing
that survives**. Don't rely on memory you don't have.

### 3. "I'll put the open work in the git commit message"
Commit messages are searchable in `git log` but not in Mnemosyne
recall. The next session's first move is usually Mnemosyne
recall, not git log. **Use Mnemosyne for agent-visible state,
git for human-visible state**.

### 4. "Importance 0.5 is fine, sleep() will keep it"
Sleep() consolidates importance 0.5 memories into 1-line
episodic summaries. The "do not consolidate" signal is high
importance (≥0.8) + `valid_until` in the future. **Use 0.85,
set valid_until to ~1 month out**.

### 5. "I'll write the canonical slot but skip the remember"
The canonical slot is single-source-of-truth, but it doesn't
surface in temporal recall. If a user asks an adjacent-but-not-
exact question, the canonical won't trigger. **Write both forms.**

## Configuration knobs

Mnemosyne's defaults are tuned for general use. For
parallel-session workflows, the recommended tunings:

```python
# When WRITING a handoff:
mnemosyne_remember(
    content="<handoff body>",
    importance=0.85,         # high, do-not-consolidate signal
    veracity="stated",       # user-confirmed, not inferred
    valid_until="<+30 days>",  # expires when stale
    source="<project>",
    extract=True,            # extract subject-predicate-object triples
                             # so mnemosyne_graph_query can find them
)
```

```python
# When READING at session start:
mnemosyne_recall(
    query="open work in-progress <project>",
    limit=5,
    temporal_weight=0.5,    # bias recent + still-valid
)
mnemosyne_recall_canonical(
    category="work",        # the canonical slot namespace
    name="in_progress",
)
```

## Related

- `session` — broader session-open/close ritual; this skill is
  the subset of `session` that handles cross-session todo
  continuity
- `mnemosyne-memory` — full Mnemosyne API surface; this skill
  uses only `remember`, `recall`, and `recall_canonical`
- `mnemosyne-curator` — memory hygiene; runs `mnemosyne_sleep()`
  which consolidates old memories. The handoff pattern is
  designed to be sleep-resistant (importance ≥0.8 + valid_until)
- `hermes-session-open-inventory` — broader pre-session
  inventory; this skill is a focused subset for todo continuity
- `routing` — profile dispatch; loaded at session start, decides
  which skills to load