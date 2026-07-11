# Reference: Cron Subsystem Dark — All 6 Jobs `last_run_at: never` (2026-07-06)

This is the deeper cousin of `mnemosyne-curator` pitfall #11 ("curator cron
is missing"). Where pitfall #11 is a **per-job** failure mode, this is a
**subsystem-wide** failure mode: every job in `jobs.json` is registered and
`enabled: true`, but NONE of them has ever fired. Re-registering the
curator won't help — the same fate will befall the new entry within 24h.

## The Symptom

```bash
cat ~/.hermes/cron/jobs.json | python -m json.tool
```

```json
[
  {
    "name": "monthly-model-research",
    "enabled": true,
    "schedule": { "kind": "cron", "expr": "0 9 1 * *", "display": "0 9 1 * *" },
    "last_run_at": "never",          ← ← ← the red flag
    "next_run_at": "2026-08-01T09:00:00",
    "state": "scheduled"
  },
  {
    "name": "weekly-knowledge-digest",
    "enabled": true,
    "schedule": { "kind": "cron", "expr": "0 10 * * 0", "display": "0 10 * * 0" },
    "last_run_at": "never",
    ...
  },
  ... 4 more entries, all `last_run_at: "never"`
]
```

If **every entry** has `last_run_at: "never"` AND the entries are 30+
days old, the cron runner has never ticked on this host. The jobs are
configured but the daemon that fires them is not running.

## The Diagnostic Ladder (Copy-Paste)

Run these in order. Each step either resolves the issue or rules out one
possibility.

### Step 1 — Confirm all jobs are `enabled: true` and have schedules

```bash
cat ~/.hermes/cron/jobs.json | python -c "
import json, sys
data = json.load(sys.stdin)
jobs = data if isinstance(data, list) else data.get('jobs', [])
print(f'Total jobs: {len(jobs)}')
for j in jobs:
    print(f\"  {j.get('name', '?'):35s} enabled={j.get('enabled')} last={j.get('last_run_at', 'never')}\")
"
```

Expected: every line shows `enabled=True` and either a real timestamp or
`never`. If anything shows `enabled=False`, the fix is a `cronjob
action='update'` to flip the flag, not a runner issue.

### Step 2 — Confirm the cron ticker file system shows activity

```bash
ls -la ~/.hermes/cron/ | grep -E "ticker|heartbeat|lock"
```

On a healthy host:
- `ticker_heartbeat` mtime is < 5 minutes old (the ticker writes here
  every cycle)
- `ticker_last_success` mtime is < 24 hours old (the most recent successful
  tick)
- No `.tick.lock` left over (a stuck lock means a tick crashed mid-flight)

If `ticker_heartbeat` is older than 5 minutes **OR** doesn't exist, the
runner is dead.

### Step 3 — Try a manual tick

```bash
hermes cron tick --once
```

This bypasses the schedule and runs the next-due job immediately. If this
succeeds (prints a job name and an "executed" line, then the job's
`last_run_at` updates), the job executor works — the scheduler is the
problem. If this errors or hangs, the executor is broken at a deeper
level (Python env mismatch, missing plugin, etc.).

### Step 4 — Check whether the ticker is supposed to be a long-lived process

```bash
# What owns the cron ticker on this host?
ps -ef 2>/dev/null | grep -iE "cron|ticker" | grep -v grep
# OR on Windows:
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python.exe'\" | Select-Object ProcessId, CommandLine"
```

The ticker can live in three places:
- A standalone daemon process (`hermes-cron-ticker` or similar) — should
  be running detached from any UI
- A child of the desktop app — only ticks while Hermes Desktop is open
- A child of `hermes serve` — only ticks while the JSON-RPC server is up
  on :9119

If the ticker is owned by the desktop app and the user closes Hermes
Desktop at night, the ticker dies — and **no jobs fire while the desktop
is closed.** This is the most common cause of "all jobs are `never`" on
a user-driven desktop install. The fix is either (a) run `hermes serve` as
a Windows service, or (b) use the OS scheduler (Task Scheduler on
Windows, launchd on macOS, systemd on Linux) to run `hermes cron tick
--once` on a fast cadence (every 1-5 minutes).

### Step 5 — Verify the OS-scheduler path works (if applicable)

If the design is "Task Scheduler runs `hermes cron tick --once` every
minute," verify the task exists and last-ran recently:

```powershell
Get-ScheduledTask -TaskName "*hermes*" -ErrorAction SilentlyContinue |
  Select-Object TaskName, State, LastRunTime, LastTaskResult
```

Expected: `State: Ready`, `LastRunTime` within the last 5 minutes,
`LastTaskResult: 0` (success). If `LastRunTime: never` or the task is
missing, this is the root cause.

## The Fix Shape

The fix depends on Step 4:

| Ticker owner | Fix |
|---|---|
| Desktop app child | Run `hermes serve` detached (Windows: Task Scheduler; Unix: systemd) |
| `hermes serve` child | Ensure `hermes serve` is running 24/7 (see `hermes serve` docs) |
| OS scheduler wrapper | Verify the OS scheduler task is enabled and running |

**Anti-pattern:** re-registering the curator cron entry when the ticker
is dead. The new entry will sit alongside the others with `last_run_at:
never` and you'll have the same problem in 24h. The fix is the runner,
not the job.

## Transcript of the 2026-07-06 Discovery

This is a condensed log of the actual session where the failure was
identified. Captures the exact commands, the path that led to the
finding, and the moment the "designed but never wired" pattern became
visible at subsystem scale (the `hermes-session-open-inventory` pitfall
#10 was about per-job, this finding elevated it to per-subsystem).

```
[session start — user asks for a deep inventory]
hermes inventory  → 6 cron jobs, all `enabled: true`
cat ~/.hermes/cron/jobs.json | python -m json.tool
  → ALL 6 jobs show `last_run_at: "never"`
  → 5 of 6 have `next_run_at` populated (the scheduler KNOWS when to fire)
  → So the scheduler is computing schedules but the executor never runs
ls -la ~/.hermes/cron/
  → ticker_heartbeat: mtime 2026-06-15 (3 weeks stale)
  → ticker_last_success: 2026-06-15
  → No `.tick.lock`
hermes cron tick --once
  → "Executing weekly-knowledge-digest..." → success
  → last_run_at updates for that one job only
  → Manual tick works; the runner just isn't scheduled
```

The next-step action was to investigate `hermes serve` ownership of the
ticker, but this session ended before the fix was applied. **Carry-over
to next session:** start by running Step 1 from this reference, confirm
the state is the same, and continue from Step 4.

## What This Skill Should Do At Cron-Fire Time

If `mnemosyne-curator` fires and discovers a stale `ticker_heartbeat`
AND no `last_run_at` on its own entry, it should NOT proceed with the
curation pass. It should emit a loud "cron subsystem dark" diagnostic
in place of the normal curator output, surface the 6-step ladder above
to the user, and exit. Running curation while the runner is dead hides
the real problem — the curator will work, but nothing else will, and
the user will see a "successful" curator alongside a silently-failing
`daily-mnemosyne-sleep`, `hermes-update-watchdog`, and the rest.

This is a self-preservation measure for the curator: if the runner is
dark, the curator's own schedule will also eventually fail, and
preserving the user-facing signal that "the cron subsystem is broken"
is more valuable than running a one-off consolidation that will get
overwritten within hours by the next `mnemosyne_remember` call.
