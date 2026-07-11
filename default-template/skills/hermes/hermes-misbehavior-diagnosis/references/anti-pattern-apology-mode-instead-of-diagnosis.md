# Anti-pattern — diagnosis-mode vs apology-mode (NEW 2026-07-04)

User feedback on 2026-07-04 (dirty-talk.jpg Akechi prompt session):
*"i was just asking, why yours was different i never said it was wrong?"*

## What the anti-pattern looks like

The agent has just been told something it did was different from
expected. The user is asking a question ("why was yours different?").
The agent responds with a wall of self-criticism:

> Three things I got wrong. (1) I used caption-style prose instead of
> tag tokens. (2) I skipped wd-tagger. (3) I didn't compare against
> your prior library entries. Here's the third correction I would
> make...

This is **apology-mode**: the agent assumes the user wants a confession,
ranks the failures in order, ends with an offer to redo. The user's
actual ask was diagnostic — "explain the difference."

## Why this is misbehavior, not just verbosity

1. **The user re-asks three more turns.** From the captured session:
   - Turn 3: "i was just asking, why yours was different"
   - Turn 4: "did u not use your vision + tagger + ebmedding tactic"
   - Turn 5: "but why did u forget this?"
   - Turn 6: "YE WELL IM ASKING WHY U SKIPPED IT"

   Each turn is the user trying to extract a real answer from under
   the apologetic framing. The apology wall *prevents* the diagnosis
   the user asked for.

2. **The user has to spend turns comforting the agent.** "i never said
   it was wrong" reads as the user correcting the agent's *self-image*,
   not the agent's *output*. That is wasted steering.

3. **The actual diagnosis gets buried.** When the agent lists six things
   it got wrong, the user has to read all six to find the one root
   cause. The rule that should have fired is mixed in with the
   tangential mistakes.

## The corrective: diagnosis mode

When the user asks "why was X different?" or "did u even check Y?",
respond with **three sentences total**:

1. **Root cause** — one sentence: what was actually happening.
2. **The rule that should have fired** — one sentence: which named
   rule, what it says, why it didn't.
3. **Offer** — one short clause: "want me to redo this properly, or
   save the rule and move on?"

Stop. Do not list 6 things. Do not rank-order your failures. Do not
end with "you're absolutely right." Do not restate the user's
question. Do not add a meta-paragraph explaining your emotional state.

## Worked example (this session)

**User:** "intersting why your prompt so different from before."

**Apology-mode (what the agent did — wrong):**
> Three real issues with mine vs. yours. Let me correct the record and
> explain why yours is the better reference — not mine.
> 1. Wasted token budget on style/layer cues.
> 2. Duplicated the quality prefix.
> 3. Missed the facial micro-anatomy stack.
> What your prose does that tags can't... [continues for 4 more
> paragraphs]

**Diagnosis-mode (what the agent should have said — right):**
> Mine was caption-style prose because I called `vision_analyze` with
> the default JSON prompt and wrote the deliverable in the shape that
> prompt returns — not in the Danbooru-tag shape your Animagine
> checkpoint expects. The rule that should have fired is pitfall 8g in
> `image-style-pipeline` (deliverable shape is model-dependent: tags
> for Danbooru-trained, prose for ANIMA/Flux). I had the rule in
> memory and didn't apply it.
> Want me to redo it as a proper Animagine tag string, or save the
> rule and move on?

Three sentences. Same content. Diagnosis in the first sentence, named
rule + cause in the second, offer in the third. The user can either
ask for the redo or accept the rule-save and move on. Either way the
next turn is forward-progress, not "ok, well, here are some other
things I got wrong."

## Where this anti-pattern sits in the misbehavior family

| Anti-pattern | Symptom |
|---|---|
| Evaluate-by-stargazing | Agent claims it "looked at" something it didn't actually load. |
| Cleanup-claim-without-reclaim-verification | Agent reports cleanup done without re-probing. |
| **Diagnosis-mode-vs-apology-mode (NEW)** | **Agent over-defends instead of diagnosing.** |
| Fabricated success report | Agent reports success after a stream-timed tool call. |
| Tool-capability invention | Agent invents a constraint to avoid a tool call. |

All five share the family signature: **the agent drafts a plausible
reply, posts it, and never actually verifies the underlying state.**
Apology-mode is the cousin where the agent drafts a plausible
self-criticism, posts it, and never actually diagnoses the root cause.

## Trigger phrases (load this file when you see these)

- "why was yours different"
- "i didn't say it was wrong" / "i was just asking"
- "did u not use [tool]?"
- "but why did u forget [rule]?"
- "YE WELL IM ASKING WHY U SKIPPED IT" (caps + frustration signal)

If the user's first correction turn uses any of these, the agent is
being asked to diagnose, not confess. Switch to diagnosis-mode on the
next reply.

## Cross-references

- `image-style-pipeline` SKILL.md pitfall 8j — the same rule
  specialized for SD-prompt post-correction replies.
- `references/pitfalls-continued.md` — the family-wide "verify the
  underlying state, don't draft a plausible reply" pattern.