# Stage Checklist — copy-pasteable for each change-shipping task

This is the per-stage checklist for the ship-pipeline skill. Use it as the worked example before/during each change.

```markdown
## CHANGE BRIEF
- Target file(s):
- Severity (LOW / MEDIUM / HIGH):
- Testable surface:

## STAGE 1 — Plan (60s)
- [ ] Verified present / verified absent / unverified / claim-prior?  → _____________
- [ ] Severity from 5-question rubric?                                → _____________
- [ ] Existing tests/verifiers identified?                           → _____________

## STAGE 2 — Small diff (5 min)
- [ ] < 3 files in this commit?
- [ ] One tool call at a time?
- [ ] One line of context above + below?
- [ ] Snapshot taken if destructive?                                  → _____________

## STAGE 3 — Tests (5 min)
### 3a. Static checks
- [ ] grep / head confirms content is what I expect?
- [ ] Dependencies present (bash / python / sqlite)?
- [ ] Cross-file references valid?
- [ ] Markdown structural sanity (fences balanced, headings counted)?

### 3b. Live checks (MEDIUM+)
- [ ] Ad-hoc verifier written to AppData\Local\Temp\hermes-verify-<topic>-<date>.py
- [ ] Verifier ran from hermes-agent venv python: /c/Users/somew/.hermes/hermes-agent/venv/Scripts/python.exe
- [ ] Verifier exited 0?

### 3c. Container rebuild (HIGH only)
- [ ] docker build mandatory (Dockerfile / requirements.txt / relay/app/*.py touched)?
- [ ] Stale-image reproduction test run?

### 3d. Cross-skill consistency (MEDIUM+)
- [ ] Version bumped in frontmatter?
- [ ] Mirrored to hermes-dist shipped template?
- [ ] Tic-row added if behavior rule?
- [ ] Cross-doc links updated?
- [ ] git diff --stat shows expected files only?

## STAGE 4 — Inspect logs (2 min)
- [ ] Verbatim PASS/FAIL output captured (not summarized)?
- [ ] Exit code 0?
- [ ] 3 fails in a row on same check → run systematic-debugging?
- [ ] auth/quota/network drift signal → surface immediately?

## STAGE 5 — Checkpoint
- [ ] All PASS → stage 6
- [ ] All MEDIUM-and-below FAIL but no blocker → commit with [VERIFIED-WITH-WARNINGS]
- [ ] Any HIGH failure → STOP. Do not commit. Recover.

## STAGE 6 — Recover or commit (5 min)
### If all-PASS or with-warnings:
- [ ] git add named files only (not more)?
- [ ] git commit -m "<summary>\n\nverification: <N> pass, <M> fail\nstage: <stage details>\nverifier: <path>"

### If FAIL or recover:
- [ ] git checkout -- <files>?
- [ ] Snapshot at ~/.hermes-state/snapshots/<topic>-<ts>/?
- [ ] failures-journal JOURNAL.md appended?
- [ ] .pre-<ts>.bak restored?
```

## Worked example: 2026-07-13 v0.4.13-default-extract (the change that exposed this gap)

```markdown
## CHANGE BRIEF
- Target files: mnemosyne-memory/SKILL.md, hermes-skill-loading-disciplines/references/agent-self-tics.md,
                hermes-dist mirror
- Severity: MEDIUM (touches auto-loaded skills, affects session-start index)
- Testable surface: tic-table substring scanner, cross-section consistency checker

## STAGE 1 — Plan
- Verified present: yes (3 of 4 source files exist)
- Severity: MEDIUM (auto-load + tic behavior rule)
- Tests: tic-table substring, frontmatter consistency, cross-doc link integrity

## STAGE 2 — Small diff
- 3 files patched (4 commits in 1 atomic group)
- Each tool call had 1-2 lines of context
- NO snapshot (no destructive change)

## STAGE 3 — Tests
### 3a. Static checks
- grep confirmed "v2.14.0" in frontmatter
- headings counted: 9 ## / 14 ### (consistent with author field)
- Code-fence balance: 310 fences (even) — PASS

### 3b. Live checks — VERIFIER MISSING ✗
- ← Here is where the pipeline broke. No ad-hoc verifier was written.
- Reason: agent thought "memory-only habit rule + pitfall + tic row" was self-evidently correct.

### 3d. Cross-skill consistency
- Broken: SKILL.md pitfall referenced "references/agent-self-tics.md" but file lives in
  hermes-skill-loading-disciplines/. Cross-link fragment not portable. FAIL.
- Pre-existing link rot: 2 other references in skill library (cross-session-context-bridge,
  cross-session-handoff-ritual-2026-07-12-this-user) are missing files.

## STAGE 4 — Inspect logs
- Stage 3 produced no output because stage 3b was skipped.
- Exit codes: n/a.

## STAGE 5 — Checkpoint — SHOULD HAVE BEEN "FAIL, recover" ✗
- Agent reported "shipped" without running the verifier.

## STAGE 6 — Recover or commit
- Stage 6a ran: git commit, but the commit message had no verifier line. ✗

## POST-MORTEM (added 2026-07-13):
- The change actually shipped clean on most fronts (frontmatter, cross-section, fenced blocks).
- But two real bugs landed in the commit:
  1. Tic-phrase literal "X" chars don't substring-match natural drafting text.
     Direct scan of tic-table phrases against 12 natural draft sentences: 5 false negatives.
  2. Cross-link "references/agent-self-tics.md" from mnemosyne-memory is broken.
- Both bugs caught by an inline substring scan run AFTER the user pushed, in the same session.
- Both fixed in amend commit bf12d79.

This is the canonical example of "what ship-pipeline is supposed to catch at stage 3, but didn't
because stage 3 didn't run."
```
