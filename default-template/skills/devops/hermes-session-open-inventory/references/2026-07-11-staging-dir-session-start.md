# Pitfall: Working-artifact path bypass — write to Downloads/<topic>_<date>/, NOT ~/.hermes-state/temp/

**Status:** CONFIRMED (worked example this session, 2026-07-11)
**Authority:** User-flagged 2026-07-11; tripwire already exists in `~/.hermes/scripts/_hermes_paths.py`

## Symptom

Agent writes Python scripts, plan docs, intermediate outputs, or `.bak` files to `~/.hermes-state/temp/<date>/` because it's an obvious "scratch" path. The convention says these go to `~/Downloads/<topic-slug>_<YYYY-MM-DD>/`. The agent has the rule in Mnemosyne but doesn't recall it at session start, and the tripwire `assert_staging_path()` only fires when the helper is called — not at every write.

## Why it bites

The Downloads convention exists for a reason: it gives every session's working artifacts a discoverable, sortable home (`~/Downloads/` lists in chronological order, matching Mnemosyne recall patterns). `~/.hermes-state/temp/` mixes session artifacts with state-archive staging, vault staging, and Hermes runtime temp files — same parent, no convention enforcement.

## How to invoke the fix

**Call `staging_dir()` as the FIRST tool call of any session**, before writing any working artifact. The helper lives in `~/.hermes/scripts/_hermes_paths.py`:

```python
from hermes_tools._hermes_paths import staging_dir, assert_staging_path
canonical = staging_dir('<topic-slug>')  # e.g. staging_dir('hermes-skill-architecture')
# Returns: ~/Downloads/<topic-slug>_<YYYY-MM-DD>/
```

Then every write in the session uses paths under `canonical`. The `assert_staging_path()` tripwire raises `RuntimeError` if a write path resolves outside this directory.

## Worked example (2026-07-11)

I wrote 13 working files to `~/.hermes-state/temp/2026-07-11/` during the skill-architecture session. User caught it: "do u not have memory of obsidan vault i said Workflow System/Decisions not to temp". Recovery: imported `staging_dir` helper, ran `shutil.move()` on the 13 files to the canonical path, soft-deleted originals to `~/.hermes-state/trash/2026-07-11/`, wrote a README at the canonical dir, committed a git-tracked mirror to the vault.

The recovery cost ~5 minutes. The bypass cost user trust and 5 minutes of supervision. **Calling `staging_dir()` at session start is the prevention.**

## When this pitfall DOESN'T apply

- Writing production skills (frontmatter patches, new SKILL.md) → `~/.hermes/skills/...` is canonical
- Writing to the vault → `~/.hermes/<VAULT_PATH>/...` per `obsidian_routing` canonical slot
- Auto-log rows → `~/.hermes/data-journal/telemetry/...` is canonical
- Trigger index → `~/.hermes/.trigger-index.json` is canonical (passive artifact)
- Snapshots of pre-destructive state → `~/.hermes-state/snapshots/...` is canonical
- Soft-deleted files → `~/.hermes-state/trash/...` is canonical

The rule applies to **session working artifacts** only: Python scripts, intermediate outputs, plan docs, .bak files. These are not Hermes state; they're the agent's scratchpad for one session.

## Related

- `~/.hermes/SOUL.md` (rule #5 covers named paths under `~/.hermes/skills/` but not session working artifacts)
- Memory `6752437e78350057` "Session-start discipline: call staging_dir() as the first tool call" (verbatim repetition of the rule; the skill captures the *why* and the *how*, the memory captures the *what*)
- `~/.hermes/docs/hermes-environment-reference-2026-07-06.md` (canonical environment reference; the Downloads convention is also documented there)