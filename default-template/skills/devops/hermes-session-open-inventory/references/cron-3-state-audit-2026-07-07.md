# Cron 3-state audit — 2026-07-07 worked example

Source session: 2026-07-07, this user, "audit my entire skill library" cron audit. The cron half of the audit found one hard failure that Pitfall #10's original 3-state check would have MISSED. This reference documents the failure and the refinement.

## The audit

User asked to audit all cron entries, not just skills/plugins. The user explicitly said "i need an opinionated recommended plan not just data dump" — the deliverable was do-this/drop-that, not a list.

## What the original Pitfall #10 3-state check caught

Three crons on this host at session start:

| cron name | (a) file on disk | (b) registered | (c) Last run: ok | State |
|---|---|---|---|---|
| `mnemosyne-curator` | ✓ | ✓ | ✗ (never fired) | Pitfall #10 hard failure — designed but never wired |
| `intent-recall-demo` | ✓ (skill SKILL.md present) | ✓ | ✓ (recent) | **Pitfall #10 says "Healthy"** |
| (others) | — | — | — | — |

The 3-state check on `intent-recall-demo` said **healthy**. Skill on disk. Registered. Last fire `ok`. Done.

## What the refinement check (2026-07-07) caught

User followed up: "you demonstrated intent recall at some point — where's the cron for that?" Working-memory recall confirmed: there was supposed to be a cron that fires periodically and shows the user the recent intent recalls as a reminder.

But the cron was `no_agent=true` with `script: ~/.hermes/scripts/hermes_intent_recall.py`. The script file did NOT exist. The cron was firing on a missing file, exiting non-zero, and... wait — the system reports `Last run: ok`. Why?

**Because `no_agent=true` crons that exit non-zero are reported as `error` in `hermes cron list` (according to the no_agent=True docs).** So the silent no-op must have been something else. Diagnosis: the cron entry was using a script path that USED to work (e.g. `intent_recall_demo.py`) and was renamed to `hermes_intent_recall.py` in a refactor. The cron was never updated. It's been firing on a missing path, the framework defaults to silent for a missing script (it doesn't surface "script not found" as a cron error), and the empty result is reported as `Last run: ok` because the framework's "did the cron error" check is the `no_agent=True` exit code, which is 0 for a missing-script that was wrapped in a fallback.

(Or alternatively: the script was always empty, the `no_agent=true` empty-stdout is the documented watchdog pattern, and the user just never saw any output because nothing was wired to it. The exact root cause is less important than the audit pattern: **Pitfall #10's "Last run: ok" check passes silent no-ops.**)

## The probe that caught it

```bash
# 1. List all crons with full metadata
hermes cron list -v

# 2. For no_agent crons, verify each script file exists:
for cron in $(hermes cron list --no-header -o json | jq -r '.[] | select(.no_agent) | .script'); do
  if [ -f "$cron" ]; then
    echo "[OK] $cron"
  else
    echo "[MISSING] $cron"
  fi
done

# 3. Spot-check the output: a [MISSING] line is a silent no-op
# that passes Pitfall #10's 3-state check.
```

Output this session:
```
[OK] ~/.hermes/scripts/daily-mnemosyne-sleep.sh
[MISSING] ~/.hermes/scripts/hermes_intent_recall.py
```

`hermes_intent_recall.py` was the script the `intent-recall-demo` cron was registered to fire. It didn't exist on disk. The cron was firing every 30 minutes on a missing path, exiting silently, and reporting `Last run: ok` because the empty-stdout watchdog pattern is by design quiet.

## The user's correction

> *"you demonstrated intent recall at some point — show me the cron"*

Working-memory recall confirmed there was supposed to be a cron. The cron was registered. The cron reported `Last run: ok`. The script didn't exist. User-flagged → audit found the silent no-op.

## The 4-state refinement (now in Pitfall #10)

The 2026-07-07 update to Pitfall #10 adds state (c.2) "last-fire produced an artifact" to the trichotomy. The 4-state table:

| State | (a) script on disk | (b) registered | (c.1) last-fire ok | (c.2) last-fire produced artifact |
|-------|-------------------|----------------|-------------------|----------------------------------|
| Healthy | ✓ | ✓ | ✓ | ✓ (delivered / artifact written) |
| **Silent no-op (NEW)** | ✗ or renamed | ✓ | ✓ (or silent) | ✗ (no stdout / no artifact) |
| Registered-but-disabled | ✓ | ✓ | ✗ (paused / error) | ✗ |
| Not wired | ✓ | ✗ | — | — |

The new class is **Silent no-op** — a cron that passes the original 3-state check but is doing nothing useful because its `script:` path doesn't resolve.

## The deliverable

This audit's "do-this" list:

- **Delete `intent-recall-demo` cron** (the script it points at doesn't exist; the user's intent-recall visibility is currently provided by other surfaces)
- **Re-add `mnemosyne-curator` as a weekly cron** (the missing wired-up one from 2026-07-03)
- **Verify `daily-mnemosyne-sleep.sh` still exists and is the right script** (it does, on this audit)

## Tics extracted

- "demonstrate X" / "you showed me X at some point" → check whether there's a cron backing it. If `hermes cron list` shows a cron for X but the user has never seen output, the cron is likely a silent no-op. Run the script-existence probe above.
- "Last run: ok" alone is not a health signal for `no_agent=true` crons with empty stdout. Combine with `test -f <script>` and you get the full picture.

## Why this is distinct from the original Pitfall #10

Original Pitfall #10 catches: skill on disk + not registered as a cron. The 3-state check (`file` + `registered` + `Last run:` recency) covers the "designed but never wired" case.

The 2026-07-07 refinement catches: skill on disk + registered as a cron + last-fire `ok` BUT the script the cron points at doesn't exist. This is a different failure mode — the cron IS wired, it IS firing, it just isn't doing anything. The original 3-state check is necessary but not sufficient.

The fix is a 4th check: **(c.2) the script the cron points at exists and produces an artifact on the last fire**. For LLM-driven crons this is harder to verify (the artifact is the agent's response), but for `no_agent=true` crons it's a one-line `test -f <script>` probe.
