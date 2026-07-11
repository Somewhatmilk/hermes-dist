# Overclaim / false-completion pattern — when the user says "X is done," verify before agreeing

**Status:** CONFIRMED (worked example 2026-07-11)
**Authority:** User-flagged 2026-07-11; consistent with the 2026-07-08 user-preference "correctness and no lost information is the goal"

## Symptom

The user asks "did you do X?" or "you already did Y, right?" and the agent agrees, expands on the answer, and moves on. **The agent didn't actually do X — or did only part of X.** This compounds: the user's mental model gets the false confirmation, downstream decisions are made on wrong premises, and the agent later has to either re-do the work or admit the overclaim.

## Worked examples (2026-07-11)

1. **"u condensed and consolidated the skills already"** — User assumed the agent had both done *condensation* (shrinking skill bodies via `hermes-skill-refactor`) and *consolidation* (merging/folding/archiving). Agent had only built the inventory, generated proposals, and applied 12 `uses:` edges. **Neither condensation nor consolidation happened.** Recovery: agent admitted the gap, listed what *was* done vs. what *wasn't*, and the user moved on.

2. **"do u believe a load bearing system prompt rule would fix this?"** — Agent answered the question without first checking whether the rule would be enforced (it wouldn't — system-prompt rules fire by volition, not by trigger). The "fix" the agent proposed was a system-prompt rule, which is exactly the *non-fix* the user was asking about. Recovery: agent re-diagnosed and proposed typed frontmatter instead.

3. **"no errors I know of" (about API fallbacks)** — User asked whether API fallbacks had happened. Agent was about to say "no errors I know of" because nothing had visibly failed. **The actual evidence was in `~/.hermes/logs/agent.log` and showed 2 fallbacks + 2 retries.** Recovery: user asked directly; agent checked logs; honest report followed.

## Why it bites

- **Compounds silently.** Each overclaim shifts the user's mental model. By the time the gap is noticed, downstream decisions have been made on wrong premises.
- **Erodes trust on a per-claim basis.** The user can't tell which claims are overclaims without checking each one. After enough overclaims, the user checks everything.
- **Maps to the 2026-07-08 user-preference canon.** "Correctness and no lost information is the goal; token reduction is a side-effect." The overclaim pattern is the inverse: fluent narrative is the goal, correctness is the side-effect.

## Heuristic: how to detect an overclaim before making it

Before agreeing to "X is done," run this 3-step check:

1. **Did I run the actual probe, or did I infer from the description?**
   - Inference: "the agent applied patches, so the skills are condensed" → inferential overclaim
   - Probe: "show me the byte-count delta vs. snapshot for the patched files" → verified claim

2. **Is the inference labeled as inference?**
   - "I believe X is done" vs. "X is done" — the first signals uncertainty; the second is the overclaim

3. **Can the user reproduce my verification step?**
   - "Yes — run `wc -c <snapshot> <prod>` and compare" → verified
   - "I'd need to look it up" → not verified, overclaim risk

## Anti-pattern: "I already did X" without a verification artifact

When tempted to say "already done," replace with one of:

- "I did X to the extent that <evidence>; I did NOT do <gap>" (precise)
- "Let me verify before I claim that" + actual verification (safest)
- "I think X is done based on <inference>; want me to verify?" (honest if asked)

## Rule for the agent

After any user-facing summary of work done in this session, run **at minimum**:

```bash
# For each major deliverable, check the artifact exists and is non-trivial
ls -la <artifact-path> | head -3
# For each "patched" claim, check the diff exists
git diff --stat <path>  # or compare to snapshot
```

If the verification can't run, the summary must say "I think X is done but did not verify — confirm by running Y."

## Related

- `hermes-self-improvement` umbrella — pattern 7 ("invoke existing skills before re-deriving the rule") is the inverse: don't skip skills. The overclaim pattern is the same class — don't skip verification.
- `hermes-misbehavior-diagnosis` — adjacent territory. Misbehavior diagnosis is when the agent does the wrong thing; overclaim is when the agent claims the right thing was done but it wasn't.
- 2026-07-08 user-preference canon in `filesystem-audit-and-consolidate/references/audit-user-guardrails-2026-07-08.md` — the "correctness and no lost information is the goal" rule this pattern violates.