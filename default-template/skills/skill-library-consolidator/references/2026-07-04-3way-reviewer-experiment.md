# 3-Way Reviewer Experiment — 2026-07-04

Session-specific detail from a controlled experiment to compare
adversary-only, reviewer-only, and combined review configurations
on the same input. Captured for pitfall #20 in
`skill-library-consolidator` SKILL.md.

## Hypothesis (pre-registered)

Different reviewer configurations catch different issue classes. My
prediction was that the combined trial would be overkill for
plan-only and the right shape only for apply-pass. The experiment
disproved the prediction: the combined trial was the only one
that produced an actionable user-facing recommendation.

## Method

Same input delivered to all three trials:

- The 2026-07-04 skill-library consolidation plan (Mnemosyne
  scratchpad `da151f3644de4eb0`)
- Plan summary covering survey numbers, contradiction detection,
  Action A/B/C/D plan rows
- Recent user-feedback context (2026-07-04 voice critique,
  2026-07-04T13:36 phrase-class correction, 2026-07-03
  prompt-size budget, 2026-06-30 invoke-existing-skills rule,
  2026-07-02 auto-log rule)

Three trials dispatched in parallel via `delegate_task`:

| Trial | Config | Goal |
|---|---|---|
| 1 | Adversary only | Standard adversary output |
| 2 | Reviewer only | JSON verdict against AC1–AC7 |
| 3 | Both (in series, single subagent) | Adversary output + JSON verdict + comparison paragraph |

Wall time and API calls measured per trial. Issues raised
counted distinct objections, not duplicates of the same finding
across trials. Severity not formally scored — but the
high-severity count is the number of Unanswered-list items the
adversary raised plus the number of blocking FAILs the reviewer
raised.

## Results

| Trial | Wall (s) | API calls | Issues | Verdict |
|---|---:|---:|---:|---|
| 1 (adversary) | 270.94 | 13 | 12 | REJECT |
| 2 (reviewer) | 308.56 | 28 | 7 | FAIL |
| 3 (both) | 372.81 | 17 | 17 | REJECT + FAIL |

**Issues caught by all three (5):**

- 4-of-5 catalog-ghost false positives (the plan's AC4 failure)
- Fold misclassification (the plan's AC2 failure)
- Archive cross-check miss (the plan's AC3 failure)
- Top-10 sum 620-byte drift
- Survey numbers off by 1–2 (166 vs 167, 170 vs 171)

**Adversary-unique findings:**

- Reframe: "the plan is the evidence of its own gaps" — the
  plan is a regression to v1.0.0 procedure
- 22-cluster and 31-category counts un-anchored (no
  bucketing rule stated)
- Mnemosyne touchpoint for archive candidates
  (pitfall #16 in the parent skill)

**Reviewer-unique findings:**

- Per-AC granularity: AC5 PASS, AC6 PASS, AC7 PARTIAL —
  structure the user needs to act on per criterion
- "Framing wrong" (AC4) vs "action wrong" distinction
- `obsidian-sd-grid-layout` path transcription error
  (`note-taking/` vs actual `productivity/`)

**Combined-trial unique value:**

- The comparison paragraph itself: "neither caught
  something the other completely missed; both are necessary;
  if forced to pick one, reviewer alone produces the verdict,
  adversary alone produces the reframe that lets you trust
  the verdict"
- All 17 issues, with overlap deduped

## Honest conclusion (matches data, not pre-registration)

The combined trial was the only one that produced an actionable
user-facing recommendation. Reviewer alone gives a FAIL verdict
but the reframe (adversary's contribution) is needed to
understand *why* the FAIL matters — the plan is regression to
v1.0.0 procedure, not a current artifact. Adversary alone
gives the reframe but the REJECT verdict without per-AC
structure leaves the user guessing what to fix.

**Combined trial's wall time (373s) is barely more than the
reviewer alone (309s).** The cost argument for skipping the
second profile doesn't hold. The real cost is the *parallel*
dispatch overhead, not the work itself.

## Recommendation for the workflow

- **Plan-only internal review** → reviewer alone is sufficient
  (FAIL on 4/7 ACs is the right shape)
- **Pre-apply review on load-time surface** → both, in series
  within a single subagent
- **Never adversary alone** as the sole gate (necessary but
  not sufficient)
- The combined trial's output shape — Adversary section +
  Reviewer section + comparison paragraph — is the
  load-bearing deliverable

## Pitfall #20 origin

This experiment is what surfaced pitfall #20 (the dispatch
context must include the output contract from
`personalities.<name>.system_prompt`, profile name alone is
not enough). All three trials produced useful output because
the dispatch context block explicitly told each subagent
which output contract to follow. Without that, subagents
dispatched via `delegate_task` would have produced a generic
review in default voice — the profile personality blocks
do NOT fire on `delegate_task` subagents.

To test the *actual* profile behavior (e.g. to A/B test the
personality tone), spawn the profile as a real subprocess:

```bash
hermes -p adversary   # or: hermes -p reviewer
```

That's the only path that activates the
`config.yaml.agent.personalities.<name>.system_prompt` block
end-to-end.

## Files

- Experiment log:
  `~/.hermes/data-journal/telemetry/3way-reviewer-experiment-2026-07-04.jsonl`
- Subagent outputs:
  `~/.hermes/cache/delegation/subagent-summary-{0,1,2}-20260704_182542_*.txt`
- Plan that was reviewed: Mnemosyne scratchpad
  `da151f3644de4eb0`
- Plan summary telemetry:
  `~/.hermes/data-journal/telemetry/skill-library-consolidation-2026-07.jsonl`
