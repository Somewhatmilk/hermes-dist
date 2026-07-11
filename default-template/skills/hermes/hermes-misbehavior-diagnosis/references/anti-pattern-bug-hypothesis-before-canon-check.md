## Anti-pattern — "Call it a NEW BUG before checking your own canon" (NEW 2026-07-06, this user)

### Failure mode (the 2026-07-06 `mcp_sequentialthinking` `mcp_tinysearch` instance)

The user asked why two MCP servers were running when they expected one. The agent surfaced-judged: *"BOTH are wrong, this is a NEW BUG in `hermes mcp list`."* The user immediately pushed back:

> *"check the current mcp servers we should have 2 if that's what u mean else if it's actually a bug reflect on our memory before making judgments"*

The agent had **already loaded the canonical resolution in turn 1** — memory `c00cb1a6` (the 2026-07-03 REFLECTION about the **two-serve gateway architecture**) — and **cited it in its first sentence**. But the very next paragraphs narrativized a "NEW BUG" hypothesis anyway, which contradicted the just-loaded memory. The agent had to walk back, check the live state, and confirm the two-serve pattern was NORMAL — exactly the scenario the REFLECTION 2026-07-03 memory described.

### The rule

**When Mnemosyne canon / a loaded reference file documents a non-obvious "this looks wrong but is normal" pattern, the agent MUST reconcile the new observation against that canon BEFORE narrating a "this is a bug" hypothesis.** Surfacing the memory is not the same as acting on it. If the memory says "two MCP servers is the expected layout, not a bug," the next user-observation about "two MCP servers" must be interpreted in that frame, not the "default frame."

This is a special case of the existing **"Memory recall ≠ rule enforcement"** pitfall in `hermes-misbehavior-diagnosis` (state 1 vs state 3 of the 4-state rule-enforcement spectrum). Memory recall gets the claim into working memory; rule enforcement is the discipline of *acting on it*. A claimed canon entry that doesn't change agent behavior is decorative.

### Why the user explicitly called it out

The user's framing — *"reflect on our memory before making judgments"* — names the discipline by name. It's a direct request to operationalize the existing recall-vs-enforcement gap: the memory exists, the user wants the next session to USE it as a precondition check, not a decorative citation.

### Diagnostic sequence when canon is loaded and a "bug?" hypothesis emerges

1. **Re-read the just-loaded canon entry (or the skill that surfaced it).** If you cited memory `c00cb1a6` two paragraphs ago and now you're narrating a "NEW BUG" that contradicts it, you have not yet read it as a *constraint* — only as *context*.
2. **Ask: "does the observation actually contradict the canon, or am I narrativizing around it?"** In the 2026-07-06 case, the canon said "two-serve is normal"; the observation was "I see two servers running." That's not a contradiction — it's the canon's predicted case. The right response was "this is the documented two-serve layout, working as intended," not "BOTH are wrong, this is a bug."
3. **If the observation truly contradicts the canon (the user is reporting something canon doesn't cover):** state the contradiction explicitly, name the canon entry, and ask whether the canon or the runtime is wrong. Don't narrativize a "bug" framing for a discrepancy that might be a canon update.
4. **If the observation is consistent with the canon:** the response is a one-liner pointing at the canon entry, not a 3-paragraph investigation. Surface-judging burns user trust faster than getting the diagnosis wrong, because the canon *was* the answer.
5. **Operationalize the canon as a precondition check.** If a memory entry will be re-loaded across many sessions (like REFLECTION 2026-07-03), promote it to a `SKILL.md` Pitfall entry so the next session loads it as a rule, not as a paragraph to be ignored. This is the state-1 → state-2 transition from `references/memory-recall-rule.md`.

### Cross-references

- **`hermes-misbehavior-diagnosis` "Pattern 7"** — the meta-pattern: a skill's own content violates its rule. The 2026-07-06 instance is a first-order application: the agent cited a canon entry, then narrated around it. The fix-loop is the same: rule says X, agent violates X, agent notices the violation, agent patches the content (or, in this case, agent + user update the canon to state-2 enforcement via this reference file).
- **`hermes-misbehavior-diagnosis` "Memory recall ≠ rule enforcement" pitfall** (in `references/memory-recall-rule.md`) — owns the abstract pattern. This file owns the "narrativized bug hypothesis despite just-loaded canon" instance.
- **`hermes-misbehavior-diagnosis` "Pitfall — Memory says v<N> of <file> exists"** (in `references/pitfall-memory-vs-file-contradiction.md`) — sibling instance: agent re-stated a version claim without re-reading the file. Same shape, different artifact (file vs observation).
- **Memory entry `c00cb1a6`** — the REFLECTION 2026-07-03 two-serve pattern that the agent failed to operationalize in 2026-07-06.

### User's exact phrasing to add to the trigger list

Add these phrases to the description of `hermes-misbehavior-diagnosis` and any future memory-vs-canon check:

- *"reflect on our memory before making judgments"*
- *"is that what we expect or is it actually a bug"*
- *"check the current X first"*
- *"we should have N if that's what u mean"*

The pattern: user is forcing a re-derivation step before a bug hypothesis. The agent must respect that pause, not narrativize past it.
