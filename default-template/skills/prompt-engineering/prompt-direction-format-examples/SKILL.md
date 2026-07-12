---
name: prompt-direction-format-examples
description: "The 5-step prompt ladder — Direction → Format → Examples → Evaluate → Divide-Labor. Use when a first-pass prompt came back wrong, when delegating to a sub-agent, or when the model picked a tone/format/length you didn't want. Do NOT use for quick clarification questions or simple lookups — those don't need a ladder."
version: 1.0.0
author: Hermes Agent (default profile, derived from r/PromptEngineering canon)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [prompt-engineering, prompting, ladder, structure, first-principles]
    category: prompt-engineering
    related_skills: [socratic-prompting, diagnose-root-cause, cartographer-prompt-gate]
    config: []
---

# Prompt Engineering Ladder (Direction → Format → Examples → Evaluate → Divide-Labor)

> **Use this skill when:** your first prompt came back wrong, OR you
> are about to ask another agent/sub-agent to do something, OR the
> model picked a tone/length/format you didn't want.
>
> **Do NOT use this skill when:** the task is a quick clarification,
> a single-fact lookup, or a copy-paste of a worked example the user
> just gave you. The ladder is overkill for those.

## The rule

A prompt has 5 dimensions. **If you skip any one of them, the model
fills the gap with its own guess, and that guess is rarely the one
you wanted.** Walk the ladder top-down:

1. **Direction** — what's the goal, who is the audience, what kind
   of decision will the output drive
2. **Format** — output shape (bullets vs prose vs table vs code),
   length (one line / one paragraph / N words), tone (formal /
   casual / direct)
3. **Examples** — 1 to 3 worked examples of what "good" looks like.
   Positive examples beat negative instructions.
4. **Evaluate** — how will you judge the output? Spell out the
   criteria so you can re-prompt with the failed criteria next time.
5. **Divide-Labor** — what does the model do, what do tools/you do?
   Don't ask the model to look something up that you could just tell
   it. Don't ask the model to write code that a tool can generate.

## When the ladder catches things you missed

| You skipped... | The model will... | What you'll see in output |
|---|---|---|
| Direction | pick a goal that matches the words, not your intent | generic, technically-correct-but-not-what-you-meant answer |
| Format | pick a format (length, tone, structure) from the model's defaults | verbose when you wanted terse; prose when you wanted bullets |
| Examples | pattern-match on whatever's in its training | inconsistent style across multi-part outputs |
| Evaluate | optimize for the wrong thing | model hits a different success criterion than you wanted |
| Divide-Labor | try to do everything itself | fabricated facts when it should have used a tool |

## Worked example

**Bad prompt (skips 3 of 5):**
> "Explain quantum entanglement to a high schooler"

**Good prompt (all 5):**
> **Direction:** Explain quantum entanglement to a high schooler who
>   is curious about physics but has only had intro chemistry. The
>   goal is intuition, not a working physicist's understanding.
> **Format:** 3 short paragraphs, plain English, one analogy from
>   everyday life, no equations, no jargon without a one-line
>   definition.
> **Examples:** Here's what "good" looks like — the kind of
>   explanation that would make the high schooler say "oh, I get it,
>   like when X". Avoid the kind of explanation that makes them say
>   "wait, what's a Hilbert space?".
> **Evaluate:** Success = the high schooler can re-explain it to
>   their friend in 30 seconds and gets the same analogy. Failure =
>   they need to look up a term to understand your explanation.
> **Divide-Labor:** The model writes the explanation. You (the
>   human in the loop) review for jargon that snuck in.

## Common failure modes

### "But I told it the format"
You said "short". The model thinks 500 words is short. **Be specific.**
Instead of "short", say "≤ 200 words" or "3 sentences max" or
"Twitter-length". Format words are subjective without a number.

### "I gave an example but it didn't follow it"
The model probably saw the example as a "this is one of many valid
styles" hint. **Add 2-3 examples, not 1.** And make them vary along
the dimension you care about (different topics, same format) so
the model pattern-matches the *format* not the *topic*.

### "It did what I asked but not what I wanted"
That's a Direction failure. The model took your words literally.
**Re-state the goal as "this output will be used for X"** — that
gives the model the meta-context to choose.

### "I keep re-prompting the same way and getting different results"
That's a Divide-Labor failure OR a missing Examples slot. Either the
task should be split between model + tool, or you need a worked
example to anchor the model.

## Anti-examples

> "Write a function to validate email addresses"

Missing: Direction (validate how — RFC-strict or practical?),
Format (return bool, raise, return cleaned string?), Examples
(show me a passed and a failed case), Evaluate (what counts as
valid), Divide-Labor (use a library?).

> "Make this email more professional"

Missing: Format (longer? shorter? same length?), Examples (show
me a before/after pair), Direction (for internal team or external
client? what tone of "professional"?).

## Related

- `socratic-prompting` — 3 questions to ask before writing a prompt
- `diagnose-root-cause` — when a fix doesn't work, the cause is usually upstream
- `cartographer-prompt-gate` — applies the ladder to the initial
  system-prompt authoring (a different problem class: prompts that
  other agents will see vs prompts you write for one task)