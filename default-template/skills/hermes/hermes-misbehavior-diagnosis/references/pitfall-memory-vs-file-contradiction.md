## Pitfall — "Memory says v<N> of <file> exists" — verify the file before repeating the claim (NEW 2026-07-04, this user)

### Failure mode (the 2026-07-04 v4-vs-v5 SOUL.md session, the SOUL.md instance)

Mnemosyne canon recorded "v5 SOUL.md removed phrase-class triggers at 03:11." The next session operated on that recall and answered the user's question as if v5 were live. The live `~/.hermes/SOUL.md` was still v4 with the triggers intact — the patch landed in `profiles/default/SOUL.md` (which the framework does not load), not in the global file the runtime reads. User pushback verbatim:

- *"v4 already does this are u referring to current or memory of v4 soul.md? it might be stale already"*
- *"hold the fuck on isnt soul.md loaded by default"*

Both corrections came because the agent re-stated the recall as if it had re-verified.

### The rule (generalize the SOUL.md instance to a class)

Any memory entry that asserts a **version, content state, or claim about a specific file** must be **re-verified with `read_file` on that file in the same turn** before the agent re-states the claim to the user.

This is a special case of the **"Symbol missing — verify which source tree"** pitfall (in `references/pitfalls-continued.md` of `hermes-misbehavior-diagnosis`) generalized from Python source trees to Mnemosyne canon. In both cases the agent has two contradictory sources of truth (one in head/recall, one on disk) and acts on the wrong one. The fix is the same: read the disk, then act on what the disk says, then fix the memory to match.

### State in the 4-state rule-enforcement spectrum

Per `references/memory-recall-rule.md`:

| State | Description | Failure mode |
|---|---|---|
| 1 | Rule in Mnemosyne only (best-effort recall) | Easily forgotten under context pressure |
| 2 | Rule in SKILL.md Pitfalls (surfaced when skill loads) | Still advisory — agent can choose to ignore |
| 3 | Rule as a precondition check (mechanical, fires before tool call) | Enforced — violation requires breaking the code |
| 4 | Rule as a hardcoded dispatch table | Strictest |

A "v<N> of <file>" claim in memory is state-1. The rule fires only if the agent re-checks state-3 (the live file on disk) before acting. Memory recall is **necessary** for the agent to consider the claim at all; it is **not sufficient** for the agent to re-state it as truth.

### Cross-references (the same incident, three angles)

- **`hermes-profile-taxonomy` v1.5.0 "Pitfall — SOUL.md version drift between memory and disk"** — owns the SOUL.md-specific instance. Includes the discipline: *"any time a memory entry claims 'v<N> of <file> exists,' the next session MUST `read_file` that file and confirm before repeating the claim."*
- **`hermes-misbehavior-diagnosis` "Symbol missing — verify which source tree" pitfall** — owns the Python-source-tree instance. Same shape (memory of X vs file reality), different layer.
- **This reference file** — owns the abstract pattern. When a new failure instance appears in the future, the diagnostic sequence below applies, and a new cross-reference gets added here.

### Diagnostic sequence before re-stating any file-version claim from memory

1. **Identify the file** the memory is making a claim about (path, name, version). If the memory doesn't name a file, the claim isn't version-shaped and this rule doesn't apply — proceed normally.
2. **`read_file` that file in the current turn.** Not last turn. Not the agent's prior session. Current turn.
3. **If the file contradicts the memory:** EITHER patch the file to match the memory's design intent (preferred when memory is the user's recorded intent and the file is just behind) OR `mnemosyne_invalidate` the stale memory and record a new one anchored to the actual on-disk content. Never both drift. Never re-state the memory as truth.
4. **If the file confirms the memory:** re-state the claim normally, with the disk evidence cited (line numbers, the actual content snippet).
5. **Never say "v<N> is live" or "the file is patched" without a same-turn `read_file` citation.** "Live" means "I just read it this turn." Anything else is hearsay.

### Anti-pattern name

**"Pattern 7"** — a warning stored in the very artifact that violates it. The phrase-class triggers in v4 SOUL.md were themselves an example of the failure mode they were supposed to flag (the agent says those phrases after deciding to ship, not before). Any time a skill or SOUL.md contains a "this is what we don't do" section, the skill MUST also verify its own content against the rule on every load. The fix-loop is: rule says X, content violates X, agent notices the violation, agent patches the content. The loop only closes if the agent's own content gets checked against its own rules — which is exactly what the diagnostic sequence above enforces.
