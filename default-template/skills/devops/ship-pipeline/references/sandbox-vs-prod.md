# Sandbox vs Prod — where to put what

Three locations the agent confuses. This reference is the disambiguation table.

## The three locations

| Location | Purpose | Lifetime | Mutable from agent? | Git-tracked? |
|---|---|---|---|---|
| `~/.hermes/sandboxes/<topic>-<ts>/` | Ad-hoc verifier runs, parallel-test subagent workspaces, scratch experiments | Hours to days; safe to delete after the change ships | Yes (full rwx) | No |
| `~/.hermes-state/snapshots/<topic>-<ts>/` | Pre-change state backups for rollback | Days to weeks (per `hermes-state-archive` retention); auto-purged per skill rules | Yes for read; write only via `preflight-snapshot-rollback` | No |
| `C:\Users\somew\hermes-dist` (or repo working copy) | The production repo. What gets committed. | Permanent | Yes for uncommitted; commits go through ship-pipeline | Yes (master + tags) |

## Decision rule

```
Is this a test/scratch run OR the prod edit itself?
├─ Test/scratch → ~/.hermes/sandboxes/<topic>-<ts>/
└─ Prod edit → ~/hermes-dist (the repo)
        └─ Was a state-touching destructive change? → ALSO ~/.hermes-state/snapshots/<topic>-<ts>/
```

In particular:

| Action | Wrong location | Right location |
|---|---|---|
| Writing the ad-hoc verifier | `C:\tmp\` (Windows /tmp path-mangle trap, per the existing skill library entry) | `C:\Users\<user>\AppData\Local\Temp\hermes-verify-<topic>-<date>.py` (MSYS /tmp via bash); or `~/.hermes/sandboxes/<topic>/verifier.py` for sandboxed runs |
| Pre-rollback backup of `config.yaml` | Anywhere | `~/.hermes-state/snapshots/<topic>-<ts>/config.yaml.pre-<ts>` AND copy of the original alongside |
| Subagent workspace for parallel testing | `C:\Users\somew\.hermes\sandboxes\verify-v0411\` | Same as above; subagent gets its own `<topic>-<ts>/` subdir |
| Final committed change | `~/.hermes/sandboxes/` (NEVER — git history is in the repo, not the sandbox) | The repo working copy; `cd /c/Users/<user>/hermes-dist && git commit` |

## The 3 sandbox dir patterns

There are actually three sandbox-like locations. Don't mix them up:

1. **`~/.hermes/sandboxes/`** — what `threat-tiered-sandbox-workflow` (memory anchor) points at. For ad-hoc verifier runs. Hard rule: do NOT sandbox under `~/.hermes/profiles/` — that's a different concept (per-user profile directories). Hard rule: do NOT sandbox under `C:\tmp\` — Windows `/tmp` MSYS path-mangle produces `C:\tmp\...` from `bash` but Python on Windows reads `C:\Python\<ver>\tmp\...`. Use `AppData\Local\Temp` (which MSYS bash sees as `/tmp`) for short-lived verifiers, `~/.hermes/sandboxes/` for cross-session ones.

2. **`~/.hermes-state/snapshots/`** — preflight-snapshot-rollback output. Pre-edit backups of state OUTSIDE git. Different from sandboxes because: it's a copy-of-original state, not a scratch workspace; it has a retention rule; it goes through `hermes-state-archive` for cleanup.

3. **`~/.hermes-sandbox/`** (singular, no trailing `es`) — the canonical hermes-state-archive container (per hermes-state-archive skill, v0.5.0). Symlink-free, hermes-managed. Distinct from `~/.hermes/sandboxes/` (plural). Stores hermes-agent snapshots, KEEP-patches, .bak/.orig/.corrupted files, strays, sandbox downloads.

## Spawning a subagent for testing (sandbox discipline)

Per the user's verbatim 2026-07-13: "You can spawn a separate agent there for ample testing."

Workflow:

1. **`delegate_task(goal=<task>, context=<specifics>, toolsets=[...], role=leaf)`**
2. **Subagent's working dir**: `~/.hermes/sandboxes/<topic>-<ts>/`. Create the dir first.
3. **Subagent's toolsets**: minimize. For pure verifier runs, `[terminal, file]`. For change-then-verify, `[terminal, file, patch, write_file]`. Don't grant more than the task needs.
4. **Subagent's role: leaf** — they cannot spawn further subagents. Avoids infinite depth.
5. **Communication pattern**: subagent's final output is a single text message containing: (a) what they ran, (b) the verifier output verbatim, (c) a single-sentence PASS/FAIL/NOT-FOUND summary.

For the parallel verifier on the v0.4.13-default-extract change (this session's `deleg_9e666d88`), the subagent is asked to find an EXISTING v0.4.11 verifier on disk and re-run it, NOT to generate a new one. Generation of new verifiers is the main thread's job; re-running is the subagent's job. The split is by phase: ship = main, verify = sub.

## Recovery: when a sandbox run goes sideways

If subagent's verifier run crashed or returned garbage:

1. Don't trust the subagent's report.
2. Re-run the verifier in the main thread. Apply stage 4 of ship-pipeline (inspect logs) directly.
3. If 3 consecutive fails on the same check: invoke systematic-debugging.
4. If the verifier itself is buggy (verifier-on-verifier failure mode, hermes-distribution-packaging Incident 8/9 from 2026-07-11): log to failures-journal and roll back via the .pre-<ts>.bak file.
5. Update the ship-pipeline SKILL.md with the new failure mode so the next session catches it earlier.

## Summary

- **Sandboxes are for verifier runs.**
- **Snapshots are for pre-edit state backups.**
- **The repo is for committed changes.**
- **Subagents live in their own sandbox subdir.**
- **Sandbox mistakes have low blast radius; repo mistakes do not. Air-gap them.**
