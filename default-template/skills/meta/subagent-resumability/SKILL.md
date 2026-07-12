---
name: subagent-resumability
description: "Pattern for subagent scratchpad checkpoints + deterministic-UID retry so blocked/killed subagents don't lose work. Use when: (a) spawning a subagent for any non-trivial task, (b) the parent has a child_timeout_seconds budget that might kill a long run, (c) the subagent might hit rate limits or server-down, (d) you want the same logical task to retry without redoing work. The wrapper tool is at ~/.hermes/scripts/subagent-with-resume.py."
version: 1.0.0
author: Hermes Agent (default profile, derived from user canon 2026-07-10 + 2026-07-12)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [subagent, leaf-agent, scratchpad, mnemosyne, resumability, retry, checkpoint]
    category: meta
    related_skills: [cross-session-todo-handoff, mnemosyne-memory, mnemosyne-tuning, mnemosyne-curator, failures-journal]
    config: []
---

# Subagent Resumability — scratchpad checkpoints + deterministic-UID retry

> **Use this skill when:** you're spawning a subagent (delegate_task) for
> any non-trivial task. Especially when:
> - the work might exceed `child_timeout_seconds` (default 1800s = 30 min)
> - the subagent might hit rate limits or server-down errors
> - you want a retry to pick up where the prior attempt left off
>
> **Do NOT use this skill when:** the task is trivial (<2 tool calls,
> clearly under 1 min) and the retry cost is lower than the checkpoint
> cost. Don't checkpoint a 30-second job.

## The problem

Per user canon (2026-07-10):

> "When a subagents get blocked, drops, 503 or rate limited it starts a
> new session again this can be observed as the same work was called twice
> with the same id, we need to be clear it should be continuing on a
> existing session if already made sticking t"

Concrete failure modes observed:
- Subagent makes 30 tool calls, discovers key IDs/paths/state
- Network blip or rate limit kills it at call 31
- Retry generates a **new subagent with a new ID** — all in-flight state lost
- The work between calls 1-30 is repeated from scratch

## The fix (3 layers)

### Layer 1: Subagent scratchpad writes (mandatory discipline)

Every subagent invocation should write to scratchpad at 4 checkpoints:

```python
# At start
mnemosyne_scratchpad_write("subagent/<uid>/goal", "<literal goal string>")

# Before each EXPENSIVE tool call (HTTP > 5s, model load, multi-file scan)
mnemosyne_scratchpad_write("subagent/<uid>/progress/<step>",
  "<exact ID, path, URL, or fact — verbatim, no summary>")

# Every 5 tool calls
mnemosyne_scratchpad_write("subagent/<uid>/checkpoint-<n>",
  "completed: <list>; remaining: <list>; key_state: <exact IDs/paths>")

# Approaching tool-call budget OR before risky call
mnemosyne_scratchpad_write("subagent/<uid>/final-state",
  "goal: <task>; completed: <list>; remaining: <list>; resume_from: <state>")
```

**Cost:** ~250 tokens overhead per subagent (5 writes × 50 tokens).
**Worth it:** <2% of typical subagent token budget; saves full re-run on retry.

### Layer 2: Deterministic UID from `(goal, context_digest)`

Same input → same UID. Different goal → different UID.

```python
import hashlib
def deterministic_id(goal: str, context: str) -> str:
    digest = hashlib.sha256(f"{goal}|{context}".encode()).hexdigest()[:16]
    return f"subagent-{digest}"
```

This means: **retrying the same task with the same context uses the same
scratchpad namespace**, so the prior progress is visible to the retry.

### Layer 3: Resumable dispatch wrapper

`~/.hermes/scripts/subagent-with-resume.py` (shipped in hermes-dist):

```bash
python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "Research X" \
  --context "background context" \
  --max-retries 5 \
  --timeout-s 900
```

What it does:
1. Computes `uid = deterministic_id(goal, context)`
2. Reads `mnemosyne_scratchpad_read("subagent/<uid>/...")` for prior state
3. Spawns subagent with prior state injected into context + scratchpad protocol
4. If subagent fails (timeout, non-zero rc), sleeps 5s, retries
5. Up to N retries; each retry sees the scratchpad state left by prior attempts
6. Logs each attempt to `~/.hermes/logs/subagent-resume.log`

## Worked example

**Goal:** "Find the 3 most-cited papers on long-context LLMs from 2026, with abstracts and citations"

**Run 1 (timeout at call 8):**
- Discovers 2 of 3 papers, writes IDs/abstracts to scratchpad
- Gets rate-limited by arxiv API
- Killed at child_timeout_seconds

**Run 2 (auto-retry, same UID):**
- Reads scratchpad: "found paper 1 (id=X, abstract=Y), paper 2 (id=Z, abstract=W)"
- Skips those 2, focuses on paper 3
- Completes in 5 tool calls instead of 13

## When to use this vs raw delegate_task

| Scenario | Use | Why |
|---|---|---|
| Trivial lookup (< 2 tool calls, < 1 min) | raw `delegate_task` | Checkpoint overhead > re-run cost |
| Medium research task (10-30 tool calls, 5-15 min) | `subagent-with-resume.py` | Resumability pays for itself on first failure |
| Long-running kanban worker (hours) | `hermes kanban create` + manual checkpoints | Different mechanism (audit trail, persistence) |
| Single retry is cheap | raw `delegate_task` | Don't add ceremony to cheap work |
| Single retry is expensive (network calls, GPU time) | `subagent-with-resume.py` | Justify the overhead |

## How subagents know they might die

**Today: they don't.** Subagents have no signal from the parent that timeout is approaching.

**Discipline-based fix (cheap):** tell every subagent goal:
```
After every 5 tool calls, write a checkpoint.
Approaching your max_iterations budget (currently 80), write final-state.
Before any tool call that might fail, checkpoint FIRST.
```

**Mechanism-based fix (medium):** add a soft-timeout warning — parent sends
`mnemosyne_remember(importance=0.85, content="subagent/<uid> will be killed in 30s")`
30 seconds before hard-killing. Subagent sees warning via recall at next turn
boundary and writes final-state.

**Best fix:** the resumable wrapper above + the discipline-based prompt
discipline. The mechanism-based fix is only worth building if you have many
subagents that routinely hit timeout.

## Applies to: kanban workers, leaf agents, AND profile-routed agents

The pattern generalizes:

| Surface | UID prefix | Use |
|---|---|---|
| Leaf agent (delegate_task) | `subagent-<hash>` | This skill's wrapper |
| Kanban worker | `kanban-<task-id>` | Already has session_id; same scratchpad discipline |
| Profile-routed (e.g. prompt-engineering) | `profile-<profile>-<session-id>` | Each profile gets its own scratchpad namespace |

The discipline is the same: **before any expensive op, checkpoint exact state.
On approaching budget, write final-state.** The UID scheme differs.

## Files

| File | Purpose |
|---|---|
| `~/.hermes/scripts/subagent-with-resume.py` | The wrapper tool |
| `~/.hermes/logs/subagent-resume.log` | Retry audit log (append-only) |
| `mnemosyne_scratchpad_*` keys with `subagent/<uid>/` prefix | The persistent state |

## Honest limitations

- **Mnemosyne scratchpad is per-profile.** If the parent agent is in
  `default` profile and the subagent inherits a different profile, the
  scratchpad write may be in the parent's bank only. Use
  `mnemosyne_shared_*` for cross-profile scratchpad if you need it.
- **`hermes delegate` CLI must be on PATH.** The wrapper shells out to it.
  Inside an interactive hermes session, `delegate_task` is the tool name;
  the CLI wraps that for script use.
- **No automatic final-state-on-kill.** If the parent kills via SIGKILL
  (immediate), the subagent can't write final-state. The retry sees empty
  scratchpad and starts fresh. This is the limit of the pattern.

## Related

- `cross-session-todo-handoff` — for cross-session (not cross-subagent) continuity
- `mnemosyne-memory` — full Mnemosyne API surface
- `mnemosyne-tuning` — recall-weight tuning; high-importance scratchpad writes surface reliably
- `failures-journal` — log failure patterns
- `mnemosyne-curator` — periodic sleep() consolidation; scratchpad writes are NOT consolidated if importance ≥ 0.85