---
name: ship-pipeline
description: "The 6-stage change-shipment workflow: plan → small diff → run tests/containers → inspect logs → checkpoint → recover. Auto-fires BEFORE any code/config/skill/file change the agent is about to make where there are existing tests or a self-classified medium/high severity risk. Composes preflight-snapshot-rollback (snapshot before destructive), hermes-session-open-inventory (verify what exists), hermes-distribution-packaging/references/hermes-verify-template.md (3-section ad-hoc verifier at AppData\\Local\\Temp\\hermes-verify-<topic>-<date>.py), failures-journal (log failures), systematic-debugging (recover). Trigger phrases: 'let me edit' / 'about to change' / 'I should modify' / 'just wrote' / 'let me change X' / 'I should update' / 'let me ship' / 'about to push' / 'just patched' — load BEFORE the change. User-stated rule (verbatim 2026-07-13): 'Any test that hasn't been exercised — medium or high severity — shouldn't need me to prompt it. You should run it, report what you did, why you did it, and whether it succeeded or failed. If it's ready to push, do it in the sandbox. You can spawn a separate agent there for ample testing.' Distinct from preflight-snapshot-rollback (which is destructive-only, no test stage). Distinct from hermes-session-open-inventory (which is verify-what-exists, not verify-after-change)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [devops, ship, change, verifier, test, checkpoint, recover, pipeline, sandboxes, sandbox]
    category: devops
    related_skills:
      - hermes-session-open-inventory
      - preflight-snapshot-rollback
      - hermes-distribution-packaging
      - failures-journal
      - systematic-debugging
      - hermes-misbehavior-diagnosis
      - hermes-skill-loading-disciplines
---

# Ship Pipeline — the 6-stage change workflow

The single reflex that wraps "I'm about to change X" into: plan → small diff → test → inspect → checkpoint → recover. Composes four partial skills (verifier template, preflight, inventory, failures-journal) into one workflow the agent MUST follow before reporting a change as "shipped."

**Origin (verbatim user feedback, 2026-07-13):**
> "Can't you verify this yourself in the sandbox? Is there a documented pipeline for this: plan → small diff → run tests/containers → inspect logs → checkpoint decisions → recover when it goes sideways? Any test that hasn't been exercised — medium or high severity — shouldn't need me to prompt it. You should run it, report what you did, why you did it, and whether it succeeded or failed. If it's ready to push, do it in the sandbox. You can spawn a separate agent there for ample testing. Has any of this been noted? Is the pipeline wired? If not, why am I still prompting for tests you already know need to run?"

## When to use this skill (tic-phrases that fire it)

Fires BEFORE the change, on draft-time phrases:

| Tic phrase | Fires when |
|---|---|
| "let me edit" / "I'm going to edit" | About to invoke `write_file` or `patch` on a tracked file |
| "about to change" / "about to modify" / "about to update" | About to change a config / skill / script / file |
| "just wrote" / "just patched" / "just changed" | Post-hoc; fires the verify-after-change reflex |
| "I should fix" / "I should update" / "let me fix" | About to invoke a fix pattern |
| "let me ship" / "about to push" / "ready to push" | About to invoke `git push`, `git commit`, or any external sync |
| "let me remove" / "about to delete" / "let me uninstall" | About to invoke destructive change |
| "let me add" / "let me create" / "I'll create" | About to create a new skill / file / config entry |

If you catch yourself drafting any of these phrases, **STOP the draft**, load `ship-pipeline` via `skill_view(name="ship-pipeline")`, follow the 6-stage workflow below, then return to the draft.

## The 6-stage workflow

### Stage 1 — Plan (≤ 60 seconds)

Before any tool call that modifies state:

1. **Inventory the change target.** Call `hermes-session-open-inventory` (or read the 4-state verification trichotomy from its SKILL.md). Determine: is the file/config/tool I'm about to change **Verified present** or **Claim of prior-session work**?
2. **Classify severity.** Per the 5-question severity rubric below. Default: if the change touches (a) a shared skill file, (b) `~/.hermes/config.yaml`, (c) any tfls state DB, (d) a script that runs at boot, (e) a hook fired by another tool → **MEDIUM**. If it touches (a) LLM-provider config, (b) install scripts, (c) cross-profile isolation, (d) shared surface DB → **HIGH**. Anything else is LOW.
3. **Identify the testable surface.** What existing tests/verifiers/checks apply? For skill changes: `mnemosyne_recall` + tic-table substring scan + cross-section grep. For code: the relevant ad-hoc verifier in `~/.hermes/skills/devops/hermes-distribution-packaging/scripts/` OR a new one off the `references/hermes-verify-template.md` recipe.

### Stage 2 — Small diff (≤ 5 minutes)

- One tool call at a time. Don't batch 5 patches into one message.
- **One line of context above and below** the change. No "rewrite this whole skill" — stage 2 means surgical.
- **Cap the change at 3 files per commit.** Cross-file consistency issues (e.g., bumping `v2.13.0 → v2.14.0` in 4 places including shipped template) are a real failure mode — don't discover them in production; run them through the verifier in stage 4.
- **Snapshot before destructive** (per `preflight-snapshot-rollback`): if the change touches state that lives outside git (SQLite DBs, env vars, login tokens), `cp` to a `.pre-<timestamp>.bak` file first.

### Stage 3 — Run tests/containers (≤ 5 minutes)

Per the severity classification from stage 1:

**LOW** — run only the static checks (stage-3a below). Skip live invocations.

**MEDIUM** — run static checks + at least one live check (stage-3a + 3b).

**HIGH** — run all four (3a/3b/3c/3d).

#### 3a. Static checks (file content)
- Does the changed file contain what you expect? (`grep`, `head`, etc.)
- Are dependencies present? (bash, python, sqlite, etc.)
- Are cross-file references still valid? (`grep -oE 'references/[a-z0-9_.-]+\.md' <file> | while read r; do test -f "$(dirname)/$r" || echo MISSING; done`)
- Markdown structural sanity: code-fence balance (even number of \`\`\` lines), cross-section consistency (heading count, version-bump presence in author field).

#### 3b. Live checks (Python or shell invocation)
Use the **3-section ad-hoc verifier pattern** from `~/.hermes/skills/devops/hermes-distribution-packaging/references/hermes-verify-template.md`:

```python
"""hermes-verify-<topic>-<DATE>.py — focused ad-hoc verification."""
import json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

# === CONFIG ===
REPO_DIR = Path(r"C:\Users\somew\hermes-dist")
# ...

# === STATE ===
passed, failed = [], []

def assert_(cond, name):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}: {name}", flush=True)

def pre_clean():
    """Idempotent cleanup so re-runs don't conflict with stale state."""
    # remove any test containers, scratch dirs
    ...

# === STATIC CHECKS ===
def check_static():
    ...
    assert_(re.search(r'^version: 2\.14\.0', text, re.M), "v2.14.0 frontmatter bump landed")

# === LIVE CHECKS ===
def check_live():
    # rebuild image, spin up container, call endpoints
    ...

# === CLEANUP + REPORT ===
pre_clean()
check_static()
check_live()
pre_clean()
print(f"\n{len(passed)} pass, {len(failed)} fail")
sys.exit(0 if not failed else 1)
```

Path convention: `AppData\Local\Temp\hermes-verify-<topic>-<date>.py`. Delete after run.

#### 3c. Container rebuild (HIGH only)
If the change touches `Dockerfile`, `requirements.txt`, `pyproject.toml`, or any `relay/app/*.py`: `docker build` is MANDATORY. Stale image reproduces pre-edit bugs.

#### 3d. Cross-skill / cross-section consistency (MEDIUM+)
For skill changes: bump version in frontmatter; mirror to shipped template (`hermes-dist/default-template/skills/...`); add to tic-table if it's a behavior rule; reference from all cross-doc links. Run `git status` and check `git diff --stat` shows the expected files.

### Stage 4 — Inspect logs (≤ 2 minutes)

After stage 3 runs:

- **Verbatim PASS/FAIL output**: print it, don't summarize.
- **Exit code check**: any non-zero exit = FAIL.
- **For three FAILs in a row on the same check**: STOP, run `systematic-debugging` skill, then log to `failures-journal`.
- **For any FAIL that signals auth / quota / network drift** (HTTP 401, 429, Connection refused): log it as a **drift signal** — these aren't bugs in your code; they're system-rot. Surface to the user immediately, don't just patch.

### Stage 5 — Checkpoint decisions (≤ 60 seconds)

After stage 4 inspects, make the call:

- **All PASS?** → stage 6 (commit + report).
- **All MEDIUM-and-below FAIL but no blocker?** → commit, label commit message with `[VERIFIED-WITH-WARNINGS]`, surface the warnings.
- **Any HIGH failure?** → STOP. Do NOT commit. Go to recover stage.

The decision is recorded in the commit body:

```
verification: 19/20 PASS, 1 FAIL (regression: tic-phrase substring match missed "logging this for later" — fixed)
```

### Stage 6 — Recover or commit (≤ 5 minutes)

#### 6a. If PASS or [VERIFIED-WITH-WARNINGS]:
- `git add` the files named in stage-3 output (not more).
- `git commit -m "<change summary>\n\nverification: <N> pass, <M> fail\nstage: <1-5 minutes of static + live checks>\nverifier: <path to ad-hoc verifier or pre-existing verifier name>"`
- **Push only if explicitly authorized by the user**. Default mode: commit, do not push. User runs `git push` themselves after seeing the diff.

#### 6b. If FAIL or recovery needed:
- **Do not commit.** Run `git checkout -- <files>` OR `git restore <files>` for any staged-but-not-committed change.
- **Snapshot the broken state** at `~/.hermes-state/snapshots/<topic>-<timestamp>/` (per `hermes-state-archive` skill).
- **Log to `failures-journal`**: append a dated entry to `~/.hermes/skills/failures-journal/JOURNAL.md` with: what was changed, what failed, why, what the next session should do.
- **Rollback if preflight snapshot exists**: `cp` the `.pre-<timestamp>.bak` files back.

## Sandbox discipline

Per the user's verbatim quote: "You can spawn a separate agent there for ample testing."

- The sandbox dir is at `~/.hermes/sandboxes/<topic>-<timestamp>/` (per threat-tiered sandbox workflow memory).
- Sandboxed tests can run in parallel via `delegate_task` with `role=leaf`. The main thread continues other work; the subagent returns its verifier output as a new message when done.
- Ship the result of verifier runs, not the planning description.

## Why each step is load-bearing (post-mortem from prior failures)

The 2026-07-13 v0.4.13-default-extract commit `b7ce0f8` shipped without running any of these stages. The user's pushback ("Can't you verify this yourself in the sandbox?") exposed two real bugs that this skill would have caught:

1. **Tic-phrase literal `X` chars don't substring-match.** Direct substring-scan of the tic-table against natural drafting text (the test that stage 3b demands for any skill change touching `agent-self-tics.md`) returned **5/12 false negatives**. The tic phrases needed to be rephrased. Fix: amend commit to `bf12d79`.
2. **Broken cross-file reference.** The new SKILL.md pitfall entry linked to `references/agent-self-tics.md`, but that file lives in a different skill (`hermes-skill-loading-disciplines/`). Direct cross-skill reference scan (stage 3d) caught it.

Both bugs would have been caught in stage 3 BEFORE commit. Both required running the verifier, not just writing it.

## Pitfalls

### Snapshot before destructive (preflight, take it seriously)

A "small change" to `~/.hermes/config.yaml` keys that the wrapper reads at boot (`api_key:` fields, `kanban.max_spawn`, `model.base_url`) requires a snapshot because Hermes doesn't watch for live changes — gateway restart is needed to reload. Get the change wrong and you have to manually `cp config.yaml.pre-<timestamp> config.yaml` to recover. **Always snapshot before editing config.yaml.**

### Don't double-fire tic-table on the same draft

If you load `ship-pipeline` from a tic, follow it through. Don't reload it on every subsequent sentence; the tic fires once per draft, not once per phrase. If you catch yourself loading the same skill twice in one turn, that's a tic-spam — note it.

### The "all green" verifier isn't always PASS

Per hermes-distribution-packaging v1.4.0 changelog (Incident 8 from 2026-07-11): "verifier's own success-path parser producing false-FAIL — `last_lines[-1]` picks 'all green' instead of the ratio line; fix via `next()` + rc=0 fallback". When parsing verifier output, never grab the last line — it can be a stray stderr echo. Always look for the explicit ratio line ("X pass, Y fail") and trust rc=0 + ratio matching.

### Don't run smoke tests against the same files the verifier checks (Incident 9)

Hermes-distribution-packaging v1.4.0 also captured Incident 9: "smoke-run against the same files the verifier checks is a TAUTOLOGY". The smoke-test must use **isolated oracles** (synthetic tree, monkeypatched globals, etc.), not the files under test.

### Sandbox-vs-prod split

`~/.hermes/sandboxes/<topic>/` is for ad-hoc verifier runs. `~/.hermes-state/snapshots/` is for state backups. Don't conflate. The sandbox can be deleted; the snapshot is durable.

## Reference files

- `references/stage-checklist.md` (NEW 2026-07-13): copy-pasteable checklist for each of the 6 stages. Pre-formatted for `tick`-table tic-row cargo culting.
- `references/cross-skill-composition.md` (NEW 2026-07-13): how ship-pipeline composes the 4 partial skills (preflight-snapshot-rollback / hermes-session-open-inventory / hermes-distribution-packaging / failures-journal). Includes the data flow diagram.
- `references/sandbox-vs-prod.md` (NEW 2026-07-13): the 3 sandbox locations, when to use which, how to delegate to a subagent for parallel testing.

## Cross-references

- `hermes-skill-loading-disciplines/references/agent-self-tics.md` — the tic row added 2026-07-13 that fires this skill at draft time
- `hermes-distribution-packaging/references/hermes-verify-template.md` — the 3-section ad-hoc verifier pattern that stage 3b uses
- `preflight-snapshot-rollback/SKILL.md` — stage 2's destructive-change handling
- `hermes-session-open-inventory/SKILL.md` — stage 1's 4-state inventory
- `failures-journal/SKILL.md` — stage 6b's failure-logging protocol
- `systematic-debugging` skill — stage 4's 3-fail-in-a-row escalation
