# Cross-skill composition — how ship-pipeline stitches 4 partial skills together

The ship-pipeline skill (`~/.hermes/skills/devops/ship-pipeline/SKILL.md`) does not invent new machinery. It composes four pre-existing partial skills into one workflow. This reference documents the data flow between them so the next session doesn't re-derive what each one does.

## The four partial skills

### 1. `preflight-snapshot-rollback` (devops)

**Role:** Stage 2 of ship-pipeline. Snapshots state before destructive changes, supports rollback if stage 3 fails.

**Trigger from ship-pipeline:** Whenever the change touches state that lives outside git:
- `~/.hermes/config.yaml` (LLM provider keys, kanban.max_spawn)
- `~/.hermes/mnemosyne/data/mnemosyne.db`
- `~/.hermes/kanban/boards/<board>/kanban.db`
- `~/.hermes/profiles/<profile>/config.yaml`
- Any `.env` file
- Any state outside git that a restart doesn't naturally fix

**Output ship-pipeline consumes:** confirmation that a `.pre-<timestamp>.bak` file exists at the original path, ready to `cp` back.

**Pitfall:** preflight-snapshot-rollback is **destructive-only**. It's NOT for testing/staging changes. Ship-pipeline gates its invocation through stage-1 severity classification: only HIGH-severity AND state-touching changes get a snapshot. For everything else, ship-pipeline skips this step.

### 2. `hermes-session-open-inventory` (devops)

**Role:** Stage 1 of ship-pipeline. The 4-state verification trichotomy ensures I know what's present before I change it.

**Trigger from ship-pipeline:** ALWAYS at stage 1, regardless of severity. Even LOW-severity changes need inventory.

**Output ship-pipeline consumes:** the inventory state of each target file (verified present / verified absent / unverified / claim-of-prior-session-work). If state is "unverified" or "claim-prior", ship-pipeline re-derives via direct file inspection before proceeding.

**Pitfall:** inventory is NOT a substitute for reading the file. It confirms presence/absence; it doesn't load content. Ship-pipeline stage 3a (static checks) is what reads content.

### 3. `hermes-distribution-packaging/references/hermes-verify-template.md`

**Role:** Stage 3b of ship-pipeline. The 3-section ad-hoc verifier pattern (CONFIG → STATE → CHECKS → CLEANUP+REPORT) and the path convention `AppData\Local\Temp\hermes-verify-<topic>-<date>.py`.

**Trigger from ship-pipeline:** MEDIUM-severity and above. SKIP for LOW.

**Output ship-pipeline consumes:** the verifier's stdout (PASS/FAIL per assertion + ratio line), exit code, and the verifier's path so it can be included in the commit message.

**Pitfall:** This file is 472 lines but ships in `references/`, NOT auto-loaded by the loader. Ship-pipeline SKILL.md tells the agent to `skill_view(name="hermes-distribution-packaging", file_path="references/hermes-verify-template.md")` at stage 3b, NOT just load `ship-pipeline`.

### 4. `failures-journal` (hermes)

**Role:** Stage 6b of ship-pipeline. When stage 3 fails AND stage 5 says "recover", failures-journal gets the post-mortem.

**Trigger from ship-pipeline:** Whenever the change is rolled back OR fails verification. Specifically when:
- `git checkout` runs to revert an uncommitted change
- A `.pre-<timestamp>.bak` is restored
- A committed change has to be reverted via `git revert`

**Output ship-pipeline consumes:** confirmation that `~/.hermes/skills/failures-journal/JOURNAL.md` has been appended.

**Pitfall:** The tic that fires failures-journal ("I just failed at X — log it") is in `agent-self-tics.md`. The tic fires the agent-self-discipline of loading the skill; it's NOT a runtime hook. Ship-pipeline's stage 6b lists the failures-journal-call in its workflow but does not depend on the tic.

### 5. `systematic-debugging` (debugging category)

**Role:** Stage 4's 3-fail-in-a-row escalation. When stage 3 produces three consecutive FAIL on the same check, ship-pipeline pauses and routes to systematic-debugging.

**Trigger from ship-pipeline:** At stage 4, if the verifier returns 3 FAIL items on the same assertion. NOT a free-form trigger.

**Output ship-pipeline consumes:** the systematic-debugging root-cause analysis result, which feeds back into stage 3 to refine the verifier.

## Data flow diagram

```
                ┌─────────────────────────────────────┐
                │  ship-pipeline skill (NEW)          │
                │  ~/.hermes/skills/devops/ship-pipeline/SKILL.md
                └─────────────────────────────────────┘
                       │ loads on tic
                       │ "let me edit"
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 1: plan                              │
       │   - hermes-session-open-inventory          │◄──── 4-state trichotomy
       │   - 5-question severity rubric             │       (verified present/absent/unverified/claim-prior)
       └─────────────────────────────────────────────┘
                       │
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 2: small diff                        │
       │   - one tool call, <3 files/commit         │
       │   - preflight-snapshot-rollback IF HIGH    │◄──── destructive-state snapshot
       └─────────────────────────────────────────────┘
                       │
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 3: tests                             │
       │   - 3a: static checks (file content)       │
       │   - 3b: live checks (verifier template)    │◄──── hermes-verify-template.md
       │   - 3c: docker rebuild (HIGH only)         │
       │   - 3d: cross-skill consistency (MEDIUM+)   │
       └─────────────────────────────────────────────┘
                       │
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 4: inspect logs                      │
       │   - FAIL pattern → systematic-debugging    │◄──── 4-phase root cause
       │   - auth/quota/network drift → SURFACE     │
       └─────────────────────────────────────────────┘
                       │
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 5: checkpoint                        │
       │   - all PASS       → commit                │
       │   - with-warnings  → commit + label        │
       │   - any HIGH FAIL  → STOP, recover         │
       └─────────────────────────────────────────────┘
                       │
                       ▼
       ┌─────────────────────────────────────────────┐
       │ Stage 6: commit or recover                 │
       │   - commit ONLY if PASS or with-warnings   │
       │   - on recover: git checkout OR git restore │
       │   - failures-journal JOURNAL.md append     │◄──── durable post-mortem
       └─────────────────────────────────────────────┘
```

## What ship-pipeline deliberately does NOT do

- **Doesn't auto-load the 4 partial skills.** The agent must call `skill_view(name=...)` for each at the right stage. The ship-pipeline SKILL.md says WHICH to load and WHEN, but doesn't load them itself (no skill can load another skill — the loader is the only thing that auto-loads).
- **Doesn't spawn subagents automatically.** Per the user's verbatim 2026-07-13: "You can spawn a separate agent there for ample testing." Spawning is allowed but optional. Ship-pipeline records the option in stage 3 (sandbox discipline section) without enforcing it.
- **Doesn't push.** Stage 6a commits but doesn't push. User runs `git push` themselves after seeing the diff. This matches the operator-stated v0.4.0 preference: "operator is FORBIDDEN from auto-applying profile-bundle updates; user runs hermes update-dist themselves after seeing a toast."
- **Doesn't auto-run verifiers in the background.** The 3-section ad-hoc verifier pattern (stage 3b) is a foreground tool call, not a cron or hook. The agent runs it in-band. The pattern is documented as `AppData\Local\Temp\hermes-verify-<topic>-<date>.py` so the user can re-run it themselves.
