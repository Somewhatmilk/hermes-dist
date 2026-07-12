---
name: profile-agent-resumability
description: "Apply the subagent-resumability discipline (deterministic UID + scratchpad checkpoints) to profile-routed agents. Use when: (a) routing a task to a specific hermes profile (e.g. software-engineering, prompt-engineering) that may exceed one session, (b) the profile agent may hit timeouts / rate limits / errors, (c) you want the next routing attempt to pick up where the prior left off. UID scheme: profile-<profile-name>-<session-id>. The v0.4.6 subagent-with-resume.py wrapper works as-is — you just supply --uid profile-<name>-<sid> on each call."
version: 1.0.0
author: Hermes Agent (default profile, derived from v0.4.6 subagent-resumability generalization)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [profile, routing, scratchpad, resumability, retry, checkpoint]
    category: meta
    related_skills: [subagent-resumability, kanban-worker-resumability, cross-session-todo-handoff, mnemosyne-tuning]
    config: []
---

# Profile-Routed Agent Resumability

> **Use this skill when:** a task is routed to a specific profile
> (e.g. `software-engineering`, `prompt-engineering`, `adversary`,
> `reviewer`) and the work might exceed one session. The next routing
> attempt should pick up where the prior left off.
>
> **Do NOT use this skill when:** the routed task is trivial (< 3 tool
> calls, clearly under 1 min) and the retry cost is lower than the
> checkpoint cost.

## The pattern (v0.4.6 subagent discipline, profile namespace)

Per `subagent-resumability` (v0.4.6), every long-running task writes
**exact-state checkpoints** to Mnemosyne scratchpad. The UID scheme
differs by surface:

| Surface | UID scheme | Why |
|---|---|---|
| Leaf agent (`delegate_task`) | `subagent-<hash>` | One-off work, no task ID |
| Kanban worker | `kanban-<task-id>` | Task ID is the natural stable key |
| Profile-routed agent (this skill) | `profile-<profile-name>-<session-id>` | Profile + session = stable key |

The **discipline** is identical. The UID scheme is the only difference.

## How profile routing works (per `routing` skill v3.1.0)

The default profile has 7 specialised profiles (per the `routing` SKILL.md):
- `default` — general queries
- `adversary` — adversarial review
- `communicate-design` — web/SEO/copy
- `model-merger` — SD/AI research
- `prompt-engineering` — system prompts
- `reviewer` — read-only artifact verification
- `software-engineering` — code/devops/plugins
- `sandbox` — experimental

The router (or the user's manual choice) decides which profile gets
a task. The profile's session has its own context window, own
toolset, own conversation history.

## The problem with profile sessions

A profile session is **bigger than a leaf agent** (it has the full
routing context, the auto-load skills, the model's full system
prompt). When it gets killed mid-task:

- All in-flight state is lost (no resumability built in)
- Re-routing starts a fresh session, re-derives prior work
- For long-running tasks (multi-hour research, large refactor) this
  is wasteful and may exceed the model's context window

The v0.4.6 discipline solves this: **the profile writes to scratchpad
before each expensive op, with the profile-name + session-id as
the UID prefix, so any future routing can read the prior state.**

## Concrete pattern (profile-routed agent dispatch)

```bash
# 1. Compute the deterministic UID
# (use session_id if you have it; otherwise hash the goal+profile)
PROFILE_UID="profile-software-engineering-$(hermes chat --source profile-se \
  -Q --max-turns 1 -q "what is your session_id" 2>&1 | grep -oE 'session_id.*[a-f0-9]{16,}')"

# 2. Dispatch with the v0.4.6 wrapper
python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "<the routed task>" \
  --context "<profile-specific context>" \
  --max-retries 5 \
  --timeout-s 3600 \
  --uid "$PROFILE_UID"

# 3. The wrapper's --source tag tells hermes-chat which profile to load
# (hermes chat --source <tag> --pass-session-id ...)
```

## Scratchpad discipline for profile-routed agents

Same as `subagent-resumability` but with profile-specific content:

```
# Initial goal
mnemosyne_scratchpad_write("profile-<name>-<sid>/goal",
  "<routed task literal string + profile context>")

# Before each expensive op
mnemosyne_scratchpad_write("profile-<name>-<sid>/progress/<step>",
  "<exact ID, path, URL — verbatim, no summary>")

# Every 5 tool calls
mnemosyne_scratchpad_write("profile-<name>-<sid>/checkpoint-<n>",
  "completed: <list>; remaining: <list>; key_state: <IDs/paths>")

# Approaching max-iterations
mnemosyne_scratchpad_write("profile-<name>-<sid>/final-state",
  "goal: <task>, completed: <exact list>, remaining: <exact list>,
   resume_from: <IDs/paths/state>")
```

## Profile-specific naming

The profile name in the UID is the **canonical profile slug** (the
value of `--profile` in `hermes profile use <slug>`):

| Profile slug | Use case | Common scratchpad entries |
|---|---|---|
| `software-engineering` | Code, devops, plugins | File paths, function names, test results |
| `prompt-engineering` | System prompts, character cards | Prompt IDs, character names, template paths |
| `adversary` | Adversarial review | Counter-arguments, missed evidence, alternative framings |
| `reviewer` | Read-only artifact verification | Verdict reasoning, criteria checks, evidence paths |
| `model-merger` | SD/AI research | Model paths, recipe parameters, layer counts |
| `communicate-design` | Web/SEO/copy | URLs, post IDs, brand voice references |
| `sandbox` | Experimental | Whatever the experiment needs |

## The re-routing flow

When a user re-asks the same question (or a router sends the same
task again):

```bash
# 1. Read the canonical slot
mnemosyne_recall_canonical(category="work", name="in_progress")
# 2. See if there's a profile-<name>-<sid> scratchpad entry for the new request
mnemosyne_scratchpad_read("profile-<name>-<sid>")
# 3. If yes, start the chat with prior state in context:
python3 ~/.hermes/scripts/subagent-with-resume.py \
  --goal "..." --context "..." --max-retries 1 --uid "profile-<name>-<sid>"
# 4. The wrapper reads prior state, the chat session resumes
```

## Cost

Same as `subagent-resumability`: ~250 tokens overhead per profile
session. For a multi-hour routed task that runs hundreds of tool
calls, that's <0.1% of total token budget. **Worth it.**

## Differences from leaf-agent resumability

| Aspect | Leaf agent (v0.4.6) | Profile-routed (this skill) |
|---|---|---|
| UID prefix | `subagent-<hash>` | `profile-<name>-<sid>` |
| Context | Inherits from parent | Includes routing context + auto-load skills |
| Tool budget | `max_iterations=80` | Same, but profile-specific skills may add overhead |
| Wrapper script | `subagent-with-resume.py` | Same (just supply different `--uid`) |
| Failure mode | Killed → re-dispatch | Profile session ended → user re-routes |

The "wrapper script" line is important: **no new script needed.** The
v0.4.6 wrapper works for all three namespaces. The only change is
the `--uid` argument.

## What this skill does NOT do

- **Does not modify the `routing` skill** — that's the parent context
- **Does not add new wrapper scripts** — `subagent-with-resume.py` works
- **Does not change how `hermes profile` works** — that's a hermes-agent
  CLI command, separate concern
- **Does not require a new hermes-agent release** — uses the same
  `hermes chat --source <tag>` mechanism that already exists

## Related

- `subagent-resumability` — the parent skill; this is the profile-namespace variant
- `kanban-worker-resumability` — the kanban-namespace variant
- `routing` (auto-load) — the profile dispatch logic
- `cross-session-todo-handoff` — for cross-session continuity
- `mnemosyne-tuning` — recall-weight tuning