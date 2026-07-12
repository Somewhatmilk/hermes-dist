---
name: diagnose-root-cause
description: "When a fix doesn't work, the cause is usually upstream — not the surface symptom. This is the meta-rule for debugging: patch the cause, not the symptom. Use when you've tried 2+ fixes and the bug persists, when fixes work but the same class of bug keeps coming back, or when an LLM/agent keeps producing the same wrong output despite re-prompting."
version: 1.0.0
author: Hermes Agent (default profile)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [debugging, root-cause, meta-rule, anti-symptomatic-fix]
    category: prompt-engineering
    related_skills: [prompt-direction-format-examples, failures-journal, socratic-prompting]
    config: []
---

# Diagnose Before Patching

> **Use this skill when:** you've tried 2+ fixes and the bug persists,
> when a "fix" works but the same class of bug keeps coming back, or
> when an LLM/agent keeps producing the same wrong output despite
> re-prompting.
>
> **Do NOT use this skill when:** the bug is well-understood and the
> fix is mechanical (typo, wrong import, missing arg). Those don't
> need diagnosis, they need typing.

## The rule

> **When a fix doesn't work, the cause is usually upstream — not the
> surface symptom. Patch the cause, not the symptom.**

The first thing you observe is rarely the thing you need to change.
Symptoms are downstream of causes, and the further downstream you
patch, the more fixes you'll need and the more breakable the system
becomes.

## How to apply (3-step)

1. **List the symptoms.** What did you actually see? (error message,
   wrong output, slow performance, weird behavior). Be concrete.
2. **List the upstream chain.** What code, prompt, or assumption
   produced those symptoms? Walk the chain backwards. At each step,
   ask "could this be wrong AND consistent with the symptoms?".
3. **Patch the highest-upstream thing that explains ALL the symptoms.**
   Not the lowest-downstream thing that's the easiest to patch.

The middle step is the one people skip. They jump to "let me try
[this fix]" without enumerating the chain, and the fix is downstream
of the real cause, so the bug comes back in a different form.

## Worked example (LLM prompt)

**Symptoms:**
- Model keeps inventing tool arguments that don't exist
- Adding "do not invent tools" doesn't help
- Adding examples of correct usage helps a little but not enough

**Upstream chain:**
- Symptom: invented tool args
- ← 1 step upstream: model doesn't know what tools exist
- ← 2 steps upstream: tool list isn't in the prompt, only mentioned
- ← 3 steps upstream: tool list lives in a config the prompt-loader
    skips on a path the loader doesn't see
- **Cause:** tool list literally isn't reaching the model's context

**Real fix:** add the tool list to the system prompt (3 steps
upstream), not "do not invent tools" (the surface symptom).

## Worked example (production bug)

**Symptoms:**
- Users see stale data in their dashboard
- Adding cache invalidation helps briefly, then staleness returns
- Refresh button doesn't always work

**Upstream chain:**
- Symptom: stale data displayed
- ← 1 step upstream: cache not invalidated
- ← 2 steps upstream: write path doesn't trigger cache invalidation
- ← 3 steps upstream: write path and cache live in different services
    that don't share an invalidation channel
- **Cause:** cross-service coordination missing

**Real fix:** add a write-side invalidation hook (3 steps upstream),
not "refresh more often" (the surface symptom).

## When this rule does NOT apply

- **Time-critical incidents.** Sometimes you patch the symptom to
  stop the bleeding and *then* diagnose. The rule is for normal
  debugging, not "the prod page is down right now".
- **Well-understood bug classes.** If you've seen this exact bug
  before and you know the cause, just patch it. The rule is for
  novel bugs and persistent bugs.
- **Symptom is the cause.** Sometimes the obvious fix IS the right
  fix (typo, wrong arg, missing file). The rule's premise is that
  symptoms have upstream causes; if the symptom is the cause, the
  rule is a detour.

## Common anti-patterns

### "Let me just add a try/except"
That's hiding the symptom. If the exception is the signal, catching
it loses the signal. **Let the exception propagate, read the trace,
find the cause.**

### "Let me add a more forceful prompt"
"That's more forceful prompt" usually means more constraints piled
on top. The cause is usually upstream: missing context, wrong format
spec, no examples. **Add the missing ingredient, not another
constraint.**

### "Let me just add more logging"
Logging at the symptom level tells you what happened, not why. If
you don't already have logging at the cause level, add it there. If
you do have it and the cause is unclear, the logging isn't pointed
at the right layer.

### "The third try fixed it"
If you tried 3 things and the 3rd one worked, you have a 1/3
chance of understanding the actual cause. **Run the failure case
again with each "fix" removed** to confirm which one is actually
necessary, and which were cargo-culted.

## Related

- `failures-journal` — log + reflect on errors (this skill is the
  *one failure* version; the journal is the *all failures* pattern)
- `prompt-direction-format-examples` — the prompt-ladder rule; often
  the "upstream cause" of bad LLM output is a missing ladder rung
- `socratic-prompting` — 3 questions to ask when a fix-and-try loop
  is leading nowhere