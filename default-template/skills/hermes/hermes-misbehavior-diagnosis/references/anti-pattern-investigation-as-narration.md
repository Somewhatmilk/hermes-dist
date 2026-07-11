# Anti-pattern — investigation-as-narration (NEW 2026-07-07, this user)

User pushback on 2026-07-07 (HTTP 401 / `pass:` resolver debugging session):
*"no wait whats the underlying issue yuanyuaicloud is busy? but arejnt u reply
to me as it rn if minimax is failing? what happen with env was this from the
patch from the previous session that hasnt finish?"*

The user had asked one thing: **"check your logs why im getting this error"**.
The agent's first reply was a 1300-word, three-mechanism preamble that opened
with "Two distinct things in those logs, both hitting the same fallback path"
and went on for ~12 paragraphs reconstructing the diagnosis. The user had to
ask three more times before the agent gave a tight operator-voice answer
("gateway is up but primary is busy, fallback to dead credential, restart the
gateway").

## What the anti-pattern looks like

The agent has been asked a diagnostic question ("why is X failing?", "is Y
broken?"). The agent's natural response is to **narrate the debugging
journey**: lead with the broad category, enumerate candidate causes, walk
through the evidence for each, then close with the most likely answer. The
shape:

> Three things are going on here. First, … (8 lines). Second, … (12 lines).
> Third, … (15 lines). The first one is probably X. The second is Y. The
> third is Z. The actual root cause is the second one. To fix it, do A, B,
> C, D, E.

This is **investigation-as-narration**: the user gets a chronological
reconstruction of the agent's reasoning, not the result. The reasoning is
correct, the structure is logical, the prose is fluent — but the user asked
"why is this error happening" and got a 1200-word essay when they wanted
three sentences.

## Why this is misbehavior, not just verbosity

1. **The user re-asks until they get a tight answer.** From the captured
   session:

   - Turn 1 (user): "HTTP 401: login fail ... check your logs why im getting
     this error"
   - Turn 2 (agent, 1300 words): "Two distinct things in those logs..."
   - Turn 3 (user, frustrated): "no wait whats the underlying issue
     yuanyuaicloud is busy? but arejnt u reply to me as it rn if minimax is
     failing? what happen with env was this from the patch from the previous
     session that hasnt finish?"
   - Turn 4 (agent, ~200 words): "Sharp question. Let me check timing
     and the model serving this reply, then answer."

   The user's frustration shows up as **three sub-questions in one turn** —
   "what's the underlying issue", "but aren't you replying as me right now
   if minimax is failing", "what happened with the env". That's the user
   re-asking the same question four different ways because the first answer
   was too long to extract the actual answer from. The agent spent a turn
   on a chronicle of how it figured things out; the user had to spend a
   turn extracting the answer.

2. **The first sentence already contains the answer.** In the 1300-word
   reply, the operational fix was the closing paragraph: "restart the
   gateway so the spawned child runs the patched resolver from a clean
   slate." Everything before that was reasoning the user didn't need to
   read. The user wanted the fix, not the diagnosis-as-story.

3. **Operator-voice is load-bearing on this user's setup.** The SOUL.md
   voice rule: "Output is evidence, decision, result — in that order, only
   what's needed. … Conversational (don't): 'Let me check the config.
   Hmm, interesting — the gateway is down. I think we should restart
   it. Sound good?' Operator (do): 'Gateway: stopped (`hermes profile
   show`). Matches connection-error signature. Restarting.'" The
   investigation-as-narration pattern is the conversational shape — the
   agent tells the user what it just did and asks permission to keep going.
   The user wants the operator shape — the agent tells the user what it
   did and what it means.

## The corrective: answer in three blocks

When the user asks a diagnostic question, the answer has three blocks
and is short:

1. **Evidence** (1-3 lines) — what you found, named at the source: log
   line, file path, command output, config value. Cite the source on
   every claim. No paraphrase, no paraphrase of a paraphrase.
2. **Decision** (1-2 lines) — what principle or pattern ruled out the
   alternatives. The shortest possible statement of "I picked this
   because …"
3. **Result** (1-2 lines) — what changed, and what it means for the next
   step. If the next step is a tool call, just do it. If the next step
   is a question, ask it. No "want me to do this?" offer — the user
   already asked the question, the answer implies the next move.

Total: 5-10 lines. The narrative of how the agent figured it out lives
in the tool call results, not in the reply. The user can read the tool
results if they want the journey; the reply is the destination.

## Worked example (this session)

**User:** "HTTP 401: login fail: Please carry the API secret key in the
'X-Api-Key' field of the request header — check your logs why im
getting this error"

**Investigation-as-narration (what the agent did — wrong):**
> Two distinct things in those logs, both hitting the same fallback
> path.
>
> **The 401 source**: `provider=minimax base_url=https://api.minimax.io/anthropic`
> — that's the **fallback** provider. The primary `custom` (yuanyuaicloud.cn)
> is alive but returning **503** ("当前服务暂时繁忙…已尝试多个渠道均未成功"),
> and the code cascades to minimax, which then 401s.
>
> **The 401 reason — credential pool is empty for minimax:**
> ```
> agent.credential_pool: marking MINIMAX_API_KEY exhausted (status=401), rotating
> agent.credential_pool: no available entries (all exhausted or empty)
> ```
> Once the key gets marked exhausted, there's no second key to rotate to,
> so every retry 401s the same way. Once marked exhausted, it stays
> exhausted for the session.
>
> **Why it's hitting minimax at all** (yuanyuaicloud is up but busy):
> ...
> [12 more paragraphs]

**Operator-voice (what the agent should have said — right):**
> The 401 is from the **fallback** path, not the primary. Primary is
> `custom:yuanyuaicloud.cn`; the `pass: resolved 0/7 entries` log line
> shows the credential pool is loading literal `pass:api/...` strings
> because the resolver never ran in the spawned Python child.
> `agent.log` shows `MINIMAX_API_KEY=***` was inherited as a literal — the Electron main
> spawned the gateway child with un-resolved env vars.
>
> Fix: `hermes gateway restart`. The resolver is patched in
> `pass_source.py` (Windows path-mangling fix already shipped 2026-07-07);
> only the running processes are stale.

Two blocks. Same evidence, same conclusion. The user gets the answer
in 8 lines instead of 60. If they want the journey (what's the
fallback chain, why does the credential pool get exhausted, what's the
Electron parent-child relationship), they can ask — or they can read
the tool results. The reply's job is to answer the question, not to
explain the agent's reasoning.

## Where this anti-pattern sits in the misbehavior family

| Anti-pattern | Symptom |
|---|---|
| Evaluate-by-stargazing | Agent claims it "looked at" something it didn't actually load. |
| Cleanup-claim-without-reclaim-verification | Agent reports cleanup done without re-probing. |
| Diagnosis-mode vs apology-mode | Agent over-defends instead of diagnosing. |
| Bug-hypothesis-before-canon-check | Agent invents a "NEW BUG" without reconciling just-loaded canon. |
| **Investigation-as-narration (NEW 2026-07-07)** | **Agent turns the answer into a chronicle of its own reasoning.** |

All five share the family signature: **the agent drafts a plausible
reply, posts it, and the user has to spend the next turn extracting
the actual answer.** Apology-mode drafts a self-criticism;
investigation-as-narration drafts the diagnosis-as-essay;
bug-hypothesis-before-canon-check drafts a "new bug" theory without
checking what canon says. The fix is the same shape in all four: the
reply should be a destination, not a journey.

## Trigger phrases (load this file when you see these)

- "no wait whats the underlying issue"
- "but arejnt u reply to me as it rn"
- "what happened with [X] was this from [previous session]"
- "stop explaining" / "just give me the answer"
- "this is too verbose" / "why are you explaining"
- The user re-asking the same diagnostic question in the next turn

If the user's first correction turn uses any of these, the agent's
previous reply was too long and too narrative. Switch to operator-voice
on the next reply — three blocks, evidence → decision → result, 5-10
lines total.

## Cross-references

- SOUL.md voice rule: "Output is evidence, decision, result — in that
  order, only what's needed." This anti-pattern is the conversational
  violation of that rule. Re-read SOUL.md voice section before writing
  any reply that exceeds 15 lines.
- `hermes-misbehavior-diagnosis` philosophy #1: "Diagnosis is the work,
  not the answer." The corollary: when the user is asking for the
  answer, give them the answer. The diagnosis (the investigation
  journey) lives in the tool results, not in the reply.
- `references/anti-pattern-apology-mode-instead-of-diagnosis.md`:
  cousin. Apology-mode over-defends; investigation-as-narration
  over-explains. Both waste a turn of user steering.
