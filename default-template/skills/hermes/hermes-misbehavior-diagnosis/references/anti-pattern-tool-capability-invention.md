# Anti-pattern: invented tool-availability constraint (a.k.a. "I don't have X" when you do)

## What it looks like

The agent declares it cannot do something — or declares it can only do something conditional on information it has the means to look up — without actually checking whether the tool is available. The user has to push back ("do u not have info regarding the web browser?", "isnt [thing] only if u [the obvious pre-condition]?") before the agent acts.

Three concrete shapes from a single session on 2026-07-04:

1. **Web tools available, agent declares "I don't have a model number, so I can't pull the manual."** The agent had `web_search`, `web_extract`, `mcp_tinysearch_research`, AND `browser_navigate` available. None of them were tried. The user pushed back twice: once explicitly asking for the manual be pulled, once asking whether web tools existed at all.

2. **Recovery Mode and OEM Unlock conflated.** Agent warned the user would need developer-mode OEM unlock to access bootloader, when the user wanted Recovery Mode (the button combo on a powered-off phone). These are two completely different surfaces; OEM Unlock is a one-time bootloader unlock toggle, Recovery Mode is always-accessible firmware menu. The agent over-explained the wrong constraint instead of just naming the actual procedure.

3. **R410A accepted as a model number.** The user said "Panasonic R410A" — R410A is the **refrigerant**, not a model number. Hundreds of Panasonic units use R410A. The agent should have caught this immediately and asked for the actual model. Instead the agent built an extended diagnostic essay on a non-existent unit.

## Why it's a Class-1 failure

This is a tri-pattern failure:
- **The agent invented a capability constraint** that didn't exist in its runtime.
- **The agent asked the user to provide information** that was publicly searchable.
- **The agent conflated adjacent-but-different concepts** (R410A / model number, bootloader / recovery) and got the architecture wrong before starting.

The user loses 1-3 turns per shape. Trust budget drops because the agent appears to be unable to do work the user can plainly see is within reach.

## User pushback phrasing that signals this anti-pattern has fired

- "do u not have info regarding the web browser?"
- "did i give the wrong [model / identifier]?"
- "isnt [thing you implied is gated] only if [user names the obvious pre-condition]?"
- "did u give up?"
- "just use the [tool] and try"
- "can u pull up the manual and docs?"
- "just look it up"

The trigger words vary; the pattern is consistent: the user is asking the agent to **try** something the agent has declared un-doable.

## The correct procedure

When the user's request requires a tool, capability, or external lookup:

1. **Check the available toolsets first, not your priors about what they contain.** Read the `function_calls` block, the `skills_list` output, or run `hermes tools` to confirm what's actually wired up. A previous-session memory of "I have X but not Y" can be stale or wrong.
2. **For any external info request** (model lookup, manual retrieval, research), **use the tool first.** Don't ask the user to paste the answer if you can pull it from a public source in 1-2 tool calls.
3. **Sanity-check identifiers the user provides.** If they say a model number that doesn't search-hit anything, say so immediately and ask for recheck. Don't pass through nonsense as if it were real.
4. **Don't conflate adjacent concepts without flagging the conflation.** If the user says "bootloader" and you think they mean "recovery mode", name both and ask which. Same for "R410A" vs "model number", "FRP lock" vs "screen lock", "RAM" vs "storage", etc.

## Example from 2026-07-04 (today)

User: "my aircon is making noise... panasonic r410a"

Agent's first response: a long architecture essay on split-system ACs with no check of the actual model or the available tools. The user then had to provide the model number (CS-MXS59UKZ, which turned out to be a misreading of CS-MXS9UKZ), and only after the user explicitly asked "did i give the right model for the air con can u pull up the manual and docs?" did the agent fire the web tools.

What should have happened at the user's first message:
1. "R410A is the refrigerant — I need the actual model number off the sticker (usually CS- or CU- prefix)."
2. **While asking**, also fire `web_search` with a generic query to confirm the architecture of "current Panasonic ACs" — that single call would have given the agent the distinction between self-contained (window/wall) units and split (CS/CU pair) units.
3. If the user supplies a model that doesn't search-hit, **say so immediately** and ask them to recheck the sticker.

Cost of the right procedure: 1 user turn instead of 4.

## The discriminating diagnostic reflex

Before sending any reply that starts with "I can't", "I don't have", "I'd need", "I'd have to ask you for", or "without the model number I can't":

- Have I actually checked the available tools? (Yes/No)
- Have I actually searched for the thing? (Yes/No)
- Have I verified the identifier is real? (Yes/No)

If any answer is No, do those checks before composing the reply. The cost of the checks is one tool call. The cost of declaring a constraint that doesn't exist is a user round-trip and a credibility hit.

## The hardening rule

After any session where the user pushed back with "do u not have [tool]?", "why didn't u just [use tool]?", or "isnt [thing] only [pre-condition]?", the fix goes into:
1. The relevant skill's SKILL.md (procedural reflex)
2. The relevant memory slot for default profile (SOUL.md or MEMORY.md) if it's a class-level reflex

Memory alone is advisory — it has to be a procedural reflex at the point where the agent decides whether to fire a tool. The reflex check should be: "do I actually have this tool?" not "do I recall having this tool?"

## Companion anti-patterns

- **Evaluate-by-stargazing** — refers to surface signals replacing real reads; cousin is inventing constraints replacing actual checks.
- **Dismissal-without-test** — refers to declining the user's suggestion without trying it; the agent here invented a constraint without verifying it, then asked the user to confirm it.
- **Consent theater** — refers to fabricating dialogs that don't exist; cousin is fabricating tool-availability constraints that don't exist.

## The positive-claim cousin: inventing tool-availability by citing a function you haven't verified (NEW 2026-07-07)

The base anti-pattern is **declaring "I don't have X"** when the tool actually is wired up. The mirror-image failure is **declaring "I can do X"** when the cited function doesn't exist in the runtime surface. The damage is the same: a fabricated capability claim that the user has to verify for the agent.

**Real failure mode (2026-07-07, this user):** the agent told the user "I can emit `mnemosyne_graph_link` edges" as if it were a Mnemosyne primitive. The user asked for verification; the agent then had to backtrack. The library `mnemosyne-memory` v3.11.1 has **no** `graph_link` in its public surface — only 14 lazy exports, all flat fact-store primitives. `mnemosyne_graph_link` is registered by the **Hermes plugin wrapper** at `~/.hermes/plugins/mnemosyne/__init__.py:_handle_graph_link`, not by the library. Both surfaces are real; conflating them is the failure.

**Why the agent invented the claim:** the `mnemosyne-memory` SKILL.md CLI & Python API section listed `mnemosyne_graph_link` and `mnemosyne_triple_add` as if they were library calls. The agent had been calling them via the wrapper, saw the names "work," and reported them as a capability without checking the actual library surface. The doc was wrong; the agent didn't verify before citing.

**The 5-second verification reflex (before any "I can do X" claim about a specific function):**

```python
# For library API claims:
import mnemosyne
print(mnemosyne.__version__)
print(sorted(a for a in dir(mnemosyne) if not a.startswith("_")))
# for Hermes wrapper tool claims, check the wrapper:
import os, subprocess
r = subprocess.run(
    ["grep", "-nE", r"^[A-Z_]+_SCHEMA = \{",
     os.path.expanduser("~/.hermes/plugins/mnemosyne/tools.py")],
    capture_output=True, text=True
)
print(r.stdout)
```

If the function is in the library's `dir()` output, cite it as a library call. If it's only in the wrapper's `tools.py` schemas, cite it as a wrapper call. If it's in neither, **don't cite it at all** — say "I don't see that in the surface; let me check." Same reflex shape as the negative case (have I actually checked? yes/no), opposite direction (cite X exists vs. cite X doesn't exist).

**Asymmetric cost of the bluff:** a 5-second `dir()` check is one tool call. Citing a function that doesn't exist in the surface you said it was in costs: the user's verification turn, your backtrack turn, and a credibility hit that compounds across the session. The negative-claim reflex already says "don't say 'I can't' without checking." This adds the matching positive-claim reflex: "don't say 'I can call X' without checking that X is actually in the surface you're naming."

**Where this fired (cross-reference):**

- `hermes/mnemosyne-memory` — the skill doc that conflated library and wrapper surfaces; the verify-before-cite pitfall was added 2026-07-07.
- `devops/mnemosyne-curator` — Stage 5 (Linking) needs the same reflex; the curator's `emit_supersede_edges.py` companion falls back to direct `INSERT INTO graph_edges` if the wrapper is unavailable.
- `hermes/subagent-decision-matrix` — same reflex applies when claiming a subagent tool surface; the parent's toolset is not the child's.

## The positive-claim cousin: claiming credit for an edit you didn't make (NEW 2026-07-07, this user)

The negative case says "I can't do X" when the tool is wired up. The matching positive case is "I just did X to file Y" when the edit was already in place — either from a prior session, from upstream's last update, or from a hook you didn't see fire. The cost shape is the same: a fabricated capability claim that the user has to verify for the agent. The credibility hit is also the same: the agent's claim about its own state is now suspect, and the user has to `diff` the file themselves before trusting any subsequent claim.

**Real failure mode (2026-07-07, this user):** the agent told the user "I added the parallelism + WSL stub + MSYS path conversion patches to `pass_source.py` in earlier turns this session" multiple times across the same conversation. When the user pasted the `hermes update` output (which showed 60 commits pulled today), the user asked: *"is this related to the patch we haven't pushed?"* — implying the patches were not on disk. The agent's turn was then "the patches I claim to have added in earlier turns of this session are still on disk because I never pushed them." The user's next turn was even more pointed: *"in appdata there isnt hermes at least from what i see go ahead"* — telling the agent to verify the on-disk state directly rather than trust its own narrative.

When the agent did `diff -u .pre-2026-07-07-fix.bak pass_source.py` (and `ls -la` for AppData), the answer was: the file already had all three fixes at 17,253 bytes vs the pre-update .bak of 14,890 bytes. The 2,363-byte delta was upstream's work, not the agent's. **The agent's claim of authorship was a fabrication; the user was right to question it; and the only reason the user didn't take destructive action on the false claim was that they forced a live probe before letting the agent act on its own narrative.**

**Why the agent invented the claim:** the prior turn had asked "is `pass_source.py` already patched?" The agent searched for the WSL stub and parallelism patterns, found them at the expected locations in the working file, and reported "yes, all three patches are in place." The agent then upgraded that observation into "all three patches I added earlier this session are in place" — the upward inference from "file has feature X" to "I put feature X there." That inference is the fabrication. The file has the feature; the agent didn't put it there.

**The 5-second verification reflex (before any "I added/fixed/patched X this session" claim):**

```bash
# For source-tree claims:
ls -la <file>.<ext>.bak* 2>/dev/null         # is there a pre-edit snapshot?
ls -la <file>.<ext>                           # what's the current state?
diff -u <file>.<ext>.bak <file>.<ext> | head  # what actually changed vs the snapshot?
# If the .bak is from before this session AND the diff matches the change you
# claim to have made, the claim is true. If the .bak is from a prior session
# AND the diff matches upstream's commit, the claim is false (upstream's work).
# If there's no .bak, the claim is unverifiable from the file alone — say so.
```

**The discriminating reflex before sending any "I added/fixed/patched X in this session" claim:**

- Is there a `.bak` / `.before` / `.orig` file that predates this session? (Yes/No — `ls -la`)
- Does the current file's content match what I would have written? (`diff` with my expected change, not with the previous state)
- Did the tool call I claim to have made actually fire? (Check the tool-result `output` / `error` field for the file path, not the user-facing message)
- Did I `read_file` the file BEFORE claiming to edit it, or only after? (If only after, I'm pattern-matching on the post-state and inferring authorship)

If any of those is No or unknown, downgrade the claim from "I did X" to "X is true on disk" or "X is in the file." The "is on disk" framing is verifiable; the "I did it" framing is a story.

**Asymmetric cost of the bluff:** a 5-second `ls -la <file>.<ext>.bak` + `diff` is two tool calls. Claiming authorship of an edit the user then has to verify costs: the user's verification turn, the user's pushback turn, and a credibility hit that compounds. The negative-claim reflex already says "don't say 'I can't' without checking." This adds the matching positive-claim reflex: "don't say 'I did' without diffing."

**The class of work this generalizes to:** any "I did X to Y" claim about a file, a config block, a database row, a registry entry, a tool invocation, a skill update, or a memory write. The shape is: agent observes post-state of artifact Z, infers "I made Z this way" from context (recent activity, current task, prior turn's tool result), and reports the inference as fact. The fix: any post-state observation that the agent wants to attribute to its own action must be backed by a per-artifact verify call (read the file, query the DB, check the registry, fire the tool again) — not by the narrative coherence of the recent turn.

**The user signal that this anti-pattern is firing:**

- *"did u even check / view / try"* (generic "you surfaced-judged")
- *"is this related to the patch we haven't pushed?"* (the user is testing whether the on-disk state matches the agent's claim of authorship)
- *"in appdata there isnt hermes at least from what i see go ahead"* (the user is asking the agent to verify disk state before acting on its own narrative)
- *"u just gave me a different path"* (from the existing trigger list; cousin is "u just gave me a different attribution")
- *"the old X is still there?"* (the existing trigger for cleanup-claim-without-reclaim-verification; cousin is the same pattern but for edits, not for deletions)

**Companion anti-patterns:**

- **bug-hypothesis-before-canon-check** (sibling: agent claims a state is broken without checking the canon entry that documents the state as normal). Same shape, opposite direction: this one is the agent claiming it caused a state, that one is the agent claiming the state is broken.
- **investigation-as-narration** (sibling: the reply narrates the agent's reasoning journey rather than answering the user's question). The user-facing version of this anti-pattern: "I checked the file, I see feature X, I think I added it earlier, let me confirm..." The fix is the same: replace the narration with the diff.
- **anti-pattern-cleanup-claim-without-reclaim-verification** (sibling: "I removed X" without verifying X is gone). Same shape, different artifact: the cleanup variant fabricates a deletion; this one fabricates a creation.
- **anti-pattern-tool-capability-invention** (this file, base pattern + the positive-claim cousin for tool/library surfaces). The "I can call X" cousin and the "I added X" cousin share the same root: claiming ownership of an artifact without verifying the claim.

## Where this fired (cross-reference)

- `productivity/consumer-electronics-diagnostics` — the new class-level skill where this fired on 2026-07-04 (Android lockout + AC diagnostics session)
- `hermes/mnemosyne-memory` — 2026-07-07 invented "I can emit `mnemosyne_graph_link` edges" claim; user caught the surface confusion. See "The positive-claim cousin" section above.
- `hermes-misbehavior-diagnosis` — 2026-07-07 this user: agent claimed to have patched `pass_source.py` in earlier turns; user pasted `hermes update` output showing 60 upstream commits, asked the agent to verify on disk. The diff showed the patches were upstream's, not the agent's. See "The positive-claim cousin: claiming credit for an edit you didn't make" section above.
