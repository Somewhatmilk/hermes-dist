---
name: prompt-interview-pattern
description: Interview the user before writing, one question at a time.
version: 1.0.0
author: Hermes Agent (r-promptengineering-top-month-2026-06-25-synthesis.md, post 4, 100 votes)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [prompt-engineering, interview, clarification, scope, requirements]
    category: productivity
    related_skills: [fable-prompt, sillytavern-card-author, prompt-evolve]
    config: []
---

# Prompt Interview Pattern

**Pattern:** "I paste a rough idea into Claude and make it interview me before it writes anything. The questions it asks are better than the draft most prompts produce." — r/PromptEngineering post 4 (100 votes, 7d ago, top of month June 2026).

**Why it works:** The default model behavior when given a vague request is to produce a "statistical average of everything ever written about the topic" — a generic, safe, useless first draft. The interview pattern forces the model to do *specific* cognitive work (asking targeted questions) before writing, which surfaces the user's actual intent.

**When to use:** Whenever the user's request is vague, multi-part, has hidden constraints, or is a "I want X but I don't know exactly what X is" type. Specifically:
- "Write me a system prompt for X" (where X is a product/feature not yet specified)
- "Make me a character" (use `sillytavern-card-author` after this)
- "Help me think through Y" (where Y is fuzzy)
- "Plan Z" (where Z is large and the user hasn't scoped it)

**When NOT to use:** When the user's request is already specific and complete. Then interview is friction.

## The template (verbatim from the post)

> "I want to create [the thing: a post, a plan, a pitch, an email]. Do not write anything yet. First interview me. Ask me one question at a time, the questions that would most change what you produce: what I actually want this to achieve, who it is really for, what I am secretly unsure about, what good looks like to me. Keep asking until you have what you need, then tell me you are ready. Only then write it. Here is my rough starting point: [paste whatever you have, however messy]"

## Why "one question at a time" matters

- A wall of questions gets half-answered. One question at a time gets fully answered.
- The user thinks harder about each question because they're not juggling the others.
- Each answer can shape the NEXT question — the interview evolves based on what the user reveals.

## The 5 question types (in priority order)

When the model decides what to ask next, it should cycle through these 5 categories. The order matters:

1. **"What does success look like?"** — Establish the goal/success criteria. Without this, every subsequent question is unanchored.
2. **"Who is this really for?"** — Force the user to name the audience. "Everyone" is not an audience. "Backend engineers at a YC-stage startup" is.
3. **"What are you secretly unsure about?"** — The most powerful question. Surfaces the user's actual anxiety. Often reveals constraints the user wouldn't have volunteered.
4. **"What does good look like to you?"** — Distinguishes "adequate" from "this is what I actually want." E.g., "good" for a marketing email might be "feels like it was written by a person, not by AI" — that constraint changes everything.
5. **"What constraints am I missing?"** — Last because it only works after the first 4 have established the shape. The user can now articulate the boundary conditions (timeline, budget, tone, length, format).

## Quick Reference

```python
# The interview prompt template (paste into a fresh chat or as a system message)
interview_template = """
I want to create {thing}. Do not write anything yet.
First interview me. Ask me one question at a time, the questions that would most change what you produce:
- what I actually want this to achieve
- who it is really for
- what I am secretly unsure about
- what good looks like to me
Keep asking until you have what you need, then tell me you are ready.
Only then write it.
Here is my rough starting point: {user_input}
"""
```

## Procedure

1. **Detect trigger:** Is the user's request vague, multi-part, or high-stakes? If yes, use the interview pattern. If no, just answer.

2. **Acknowledge the trigger briefly:** "Before I write this, I want to make sure I understand. A few questions."

3. **Start with goal/success:** "What does success look like for this?" Wait for the answer.

4. **Move to audience:** "Who is this really for?" Wait.

5. **Move to uncertainty:** "What are you secretly unsure about?" Wait.

6. **Move to 'good':** "What does good look like to you, specifically?" Wait.

7. **Move to constraints:** "What constraints should I know about — timeline, format, length, tone, anything?" Wait.

8. **After 5-7 questions (or when answers start repeating):** "Got it. I'm ready to write now. Here's what I'm going to produce: [1-line summary]. Starting now."

9. **Then write.** Don't keep interviewing. The interview pattern is a SCOPE tool, not a procrastination tool.

## Pitfalls

- **Do NOT ask more than 7-10 questions.** The user will get tired. If you don't have what you need after 7, write what you have and flag the gaps.
- **Do NOT ask multi-part questions** ("What audience and what success criteria?"). One question at a time, always.
- **Do NOT skip "secretly unsure about."** This is the highest-value question. It surfaces what the user wouldn't otherwise say.
- **Do NOT keep interviewing after you've said "I'm ready to write."** That's the signal. Honor it.
- **Do NOT use this pattern when the user has been explicit.** "Write a function that takes a list of dicts and returns the dict with the max value of the 'score' key." is a complete spec. Don't interview.
- **Do NOT interview the user about their own goals** (the "I want to learn X" case). The interview pattern is for CREATION tasks. For learning, use `fable-prompt` instead.
- **NEW 2026-07-12 (this user, anti-loop):** **Do NOT re-ask when the user has already chosen from a menu you gave them.** The `clarify` tool's "Other" option is a safety hatch, not a license to re-prompt. If the assistant enumerated 2-4 options and the user replied "go with A" / "do all A" / "all A" / "go ahead" / "yes do that" — the decision is made. Execute the option. Re-listing the options ("just to confirm, you want A which means... right?") is friction, not confirmation. The same applies to numbered-list questions where the user picked a number. The interview pattern ended the moment the user picked.

## The complement: "user has decided" → execute (NEW 2026-07-12, this user)

The interview pattern handles the **vague request** case (user doesn't know what they want). The complement handles the **decided request** case (user knows what they want, picked it, said "go"). The two together form a 2-axis decision rule:

| Vague vs Decided | When | Right move |
|---|---|---|
| **Vague** | User says "I want X" without specifying what X is | Interview (this skill) |
| **Decided via menu** | User picked option N from the options you gave them | Execute, no re-asking |
| **Decided via freeform** | User said "do X" without going through a menu | Execute, no interview |
| **Ambiguous after decision** | User said "go" but the action has irreversible side effects | One-line "I'll proceed by doing X. If wrong, undo is Y." — then execute |

The failure mode this fixes: the user gives a clear "go with A" signal, the assistant pauses to re-confirm or re-list the options, the user has to say "yes, I already said A" — wasted turn, friction, and a quiet "stop asking me" signal that the assistant's interview pattern did NOT cause but WILL be blamed for.

**The diagnostic when in doubt:** if the user's last message is shorter than your last message, they're done talking. Act. If the user's last message is LONGER than your last message, they're still negotiating. Ask.

**Tic phrases that mean "user has decided, execute now" (Class 5 — agent self-tic):**
- The user writes "go with [option]" / "all A" / "do that" / "yes that" / "proceed" / "go ahead" / "execute" / "make it so" / "ship it" / "approved" — and you've already enumerated options they could be picking from. **Execute. Do not re-list the options.**
- The user writes "just do it" / "stop asking" / "you decide" / "I trust you" — execute your best guess, do not re-prompt.
- A user turn contains the word "yes" or "right" or "correct" as the answer to a question you asked — that's a confirmation, not a license to ask another question.

## Connection to other skills

- **sillytavern-card-author** uses the interview pattern as step 1 (5 questions before drafting the card)
- **fable-prompt** is the inverse: instead of asking the user questions, you ask the model to make the USER do the cognitive work
- **prompt-evolve** is post-creation: after the user accepts a draft, run GEPA against it to surface variants

## Source

- r/PromptEngineering post 4: https://www.reddit.com/r/PromptEngineering/comments/1u843xd/ (100 votes, 7d ago, top of month)
- 100-prompt version hosted at promptwireai.com/100things (referenced in the post)
- Pattern name: "interview before write" (community-coined)
- Synthesis: `C:/Users/somew/Documents/hermes-research/ocd-projects/hermes-analysis/research/prompt-engineering/r-promptengineering-top-month-2026-06-25-synthesis.md`