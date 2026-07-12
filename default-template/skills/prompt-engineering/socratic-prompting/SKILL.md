---
name: socratic-prompting
description: "3-questions pattern for strategic work — ask (1) what's the real goal, (2) what constraints am I missing, (3) what's the smallest version I can test — BEFORE doing the task. Use for architecture decisions, scope questions, anything that will cost >1 hour if you start wrong, or any task where the user's stated goal might not be the actual goal. Do NOT use for time-critical incidents or trivial decisions — those need action, not questioning."
version: 1.0.0
author: Hermes Agent (default profile, derived from r/PromptEngineering canon)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [prompt-engineering, planning, scoping, decision-making, socratic]
    category: prompt-engineering
    related_skills: [prompt-direction-format-examples, diagnose-root-cause, cartographer-prompt-gate]
    config: []
---

# Socratic Prompting — 3 Questions Before Strategic Work

> **Use this skill when:** the task is a strategic decision, will cost
> > 1 hour if you start wrong, OR the user's stated goal might not be
> the actual goal.
>
> **Do NOT use this skill when:** the user is in a time-critical
> incident (just act), the decision is trivial (just decide), or
> the user has explicitly said "I already know what I want, just
> do it" (then the right move is to do it).

## The 3 questions

Before doing the task, ask these three. Often the answer to Q1
invalidates the whole task as you understood it.

### 1. What's the real goal?

Not the stated one. The *real* one. Stated goals are often
proxies: "build a dashboard" might really mean "stop getting
asked in standup whether the system is healthy". The dashboard is
a means; the standup question is the goal.

Push past one level: ask "what does success look like for the
*person who asked*?" and "what does success look like for the
*end user*?". If those two answers differ, the stated task is
probably the wrong task.

### 2. What constraints am I missing?

Three kinds of constraints get missed:

- **Time**: "I need this Friday" with a 3-week-shaped task
- **Skill/policy**: "I want a real-time streaming response" with
  a system that does polling-only
- **Existing context**: "Just add this feature" when the feature
  already exists in a form the user forgot about

The "missing" constraints are the ones that bite you 2 hours
into the work. List them upfront.

### 3. What's the smallest version I can test?

If you can deliver 20% of the value in 5% of the time, do that
first. Then ask the user if the 20% worked, before building the
other 80%. The smallest version is also a forcing function for
*what is the value*: if you can't name a small version, you
don't know what the value is.

## When to use the answers

The 3 questions are not a "research" step. They take 2-5 minutes
max. The output is a one-line answer per question, then act.

```
Q1: Real goal = X (not the stated Y)
Q2: Hidden constraints = A, B, C
Q3: Smallest version = Z (deliverable in <1 hour)
→ Act on Z, then ask if it matches the real goal.
```

If the user already gave you the answers in their original prompt
("I need this by Friday, this is for the audit, just give me a
script I can run"), don't re-ask. The 3 questions are for when
the answers are missing or implicit.

## Worked example

**Task:** "Build me a monitoring dashboard for the API"

**Bad move:** start designing the dashboard, pick charts, choose
a stack.

**Socratic move:**
```
Q1: What's the real goal?
  → "I want to know when something is wrong before customers
     email me about it." Dashboard is a proxy for alerts.
Q2: What constraints am I missing?
  → User mentioned "API" but didn't say which one (production,
     staging?). User didn't say who looks at this (just them,
     their team, on-call rotation?).
Q3: Smallest version I can test?
  → One alert ("API p99 latency > 500ms") sent to a Slack
     channel. That's < 1 hour. Dashboard comes after the user
     confirms alerts are the right shape.
```

Result: ship the alert, not the dashboard. User is happy because
their real goal (know-before-customers) is met. Dashboard might
never be built — and that's fine, because it wasn't the real goal.

## Anti-examples

### "Just get me the answer, don't question me"
If the user is frustrated and has been burned by analysis-paralysis
before, **don't use the 3 questions**. Use the direct-prompt ladder
instead. The Socratic pattern is for *constructive* questioning, not
*obstructive* questioning.

### "I already know the constraints, just build it"
Then skip Q2 and Q3 and go. The skill's value is in the questions
that surface MISSING info, not in re-asking about KNOWN info.

### "The smallest version is the full version"
Some tasks don't decompose. A "make this Python 2 codebase work
in Python 3" task isn't amenable to a 5% slice. For those, the
3 questions are: "is this worth doing at all?" and "is there a
better path than porting?". If the answer is "no, just port it",
skip the pattern and go.

## Related

- `prompt-direction-format-examples` — the 5-step prompt ladder; the
  Socratic pattern is a *preprompt* skill (ask before writing the
  prompt), the ladder is a *prompting* skill (structure the prompt
  once you have it)
- `diagnose-root-cause` — when a fix-and-try loop is leading nowhere,
  the missing step is usually one of these 3 questions
- `cartographer-prompt-gate` — the system-prompt-authoring version:
  "what's the smallest prompt that does the job" before writing
  50 KB of prompt that does everything