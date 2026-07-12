---
name: kanban-worker-resumability
description: "Apply the subagent-resumability discipline (deterministic UID + scratchpad checkpoints) to kanban workers. Use when: (a) dispatching a kanban task that may take longer than one daemon pass, (b) the worker may hit rate limits / network issues / timeouts, (c) you want a re-dispatch to pick up where the prior attempt left off. UID scheme: kanban-<task-id>. The v0.4.6 subagent-with-resume.py wrapper works as-is — you just supply --uid kanban-<task-id> on each call."
version: 1.0.0
author: Hermes Agent (default profile, derived from v0.4.6 subagent-resumability generalization)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [kanban, worker, scratchpad, resumability, retry, checkpoint]
    category: meta
    related_skills: [subagent-resumability, profile-agent-resumability, cross-session-todo-handoff, mnemosyne-tuning]
    config: []
---

# Kanban Worker Resumability

> **Use this skill when:** a kanban task might not finish in one daemon
> pass, and you want the next dispatch to pick up where the prior left off.
>
> **Do NOT use this skill when:** the task is trivial (< 3 tool calls,
> clearly under 1 min) and the retry cost is lower than the checkpoint cost.

## The pattern (v0.4.6 subagent discipline, kanban namespace)

Per `subagent-resumability` (v0.4.6), every long-running task writes
**exact-state checkpoints** to Mnemosyne scratchpad. The UID scheme
differs by surface:

| Surface | UID scheme | Why |
|---|---|---|
| Leaf agent (`delegate_task`) | `subagent-<hash>` | One-off work, no task ID |
| Kanban worker | `kanban-<task-id>` | Task ID is the natural stable key |
| Profile-routed agent | `profile-<profile>-<session-id>` | Profile + session = stable key |
| **Kanban (this skill)** | `kanban-<task-id>` | Same as above |

The **discipline** is identical. The UID scheme is the only difference.

## Concrete pattern (kanban worker dispatch)

```bash
# 1. Compute the deterministic UID
KANBAN_UID="kanban-$(hermes kanban show <task_id> | jq -r '.id')"

# 2. Dispatch with the v0.4.6 wrapper
python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "$(hermes kanban show <task_id> | jq -r '.description')" \
  --context "$(hermes kanban show <task_id> | jq -r '.spec')" \
  --max-retries 5 \
  --timeout-s 1800 \
  --uid "$KANBAN_UID"

# 3. On success, mark the kanban task complete
hermes kanban complete <task_id> --result "..." --summary "..."
```

## Scratchpad discipline for kanban workers

Before each **expensive** tool call (HTTP > 5s, model load, multi-file scan), the worker writes:

```
mnemosyne_scratchpad_write("kanban-<task-id>/progress/<step>",
  "<exact ID, path, URL, or fact you just discovered — verbatim, no summary>")
```

Every 5 tool calls, write a checkpoint:

```
mnemosyne_scratchpad_write("kanban-<task-id>/checkpoint-<n>",
  "completed: <list>; remaining: <list>; key_state: <exact IDs/paths>")
```

Approaching the tool-call budget (within 3 of `max_iterations=80`):

```
mnemosyne_scratchpad_write("kanban-<task-id>/final-state",
  "goal: <task>, completed: <exact list>, remaining: <exact list>,
   resume_from: <exact IDs/paths/state needed to continue>")
```

Before any tool call that might fail (rate-limited API, network, server-down):

> **Checkpoint FIRST** so the next retry has your prior progress even
> if this call kills you.

## Why kanban specifically benefits

Kanban workers have **already-persistent state** (the task row in
kanban.db) that leaf agents don't. The resume discipline complements
this:

| Layer | What it persists | When it's checked |
|---|---|---|
| kanban.db (existing) | Task status, comments, events | `hermes kanban list` |
| Mnemosyne scratchpad (this skill) | Mid-run exact state, IDs, paths | Session-start recall |
| Chat session_id (`hermes chat --resume`) | Conversation history | `hermes chat --resume <sid>` |

The kanban row tells you "task X is in_progress." The scratchpad
tells you "I was on step 4 of 7, found IDs A/B/C, need to do D/E/F."
The chat session tells you "I was using this model with this system
prompt and these tools." Three layers, three purposes.

## The re-dispatch flow

When the daemon sees a task that has been in_progress for too long:

```bash
# Daemon (or human) detects stale task
hermes kanban list --status in_progress --older-than 30m
# -> task t_abc123

# Re-dispatch with the same UID
KANBAN_UID="kanban-t_abc123"
hermes kanban reclaim t_abc123  # reset the claim

python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "..." --context "..." \
  --max-retries 5 --timeout-s 1800 \
  --uid "$KANBAN_UID"
# The wrapper reads kanban-t_abc123/* from scratchpad, sees the prior
# progress, and starts the chat session with the prior state in context.
```

## Integration with `hermes kanban dispatch`

The existing `hermes kanban dispatch` daemon reads tasks from
`status='ready'` and spawns a profile to work them. To add resumability:

1. Before `kanban dispatch` spawns a worker, the worker injects
   `kanban-<task-id>/goal` into scratchpad
2. The worker runs the v0.4.6 discipline
3. If the worker is killed, scratchpad has the state
4. Next dispatch sees the prior state via the v0.4.6 wrapper

This is a small change to `kanban dispatch` (~10 lines of pre-spawn
glue), not a redesign. **Don't rewrite the daemon** — extend it.

## Cost

Same as `subagent-resumability`: ~250 tokens overhead per worker
run. For a kanban worker that runs 30-50 tool calls, that's <1% of
worker token budget.

## What this skill does NOT do

- **Does not modify `hermes kanban` daemon** — that's a hermes-agent
  change, not a hermes-dist change
- **Does not add new wrapper scripts** — `subagent-with-resume.py`
  already works for kanban namespace; you just supply `--uid kanban-<task-id>`
- **Does not change the kanban DB schema** — the task ID is already
  the natural key; we're just using it as the scratchpad UID prefix

## Related

- `subagent-resumability` — the parent skill; this is the kanban-namespace variant
- `profile-agent-resumability` — the profile-namespace variant
- `cross-session-todo-handoff` — for cross-session continuity, separate concern
- `mnemosyne-tuning` — recall-weight tuning; high-importance scratchpad writes surface reliably