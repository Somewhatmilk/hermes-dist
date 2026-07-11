# Recurring Failure Patterns on This Host

Verified incidents from JOURNAL.md, Mnemosyne, and failures-journal dated
2026-07-11. **All patterns have fired 3+ times on this host.** Cite these
at session start before doing operations in the same class.

---

## Pattern A: Subagent Consolidation-Message Gap (4th time)

### When it fires

- `delegate_task` returns a `delegation_id` immediately
- Work completes (output files written)
- The "consolidated results re-enter the conversation as a single message"
  never arrives
- Agent treats as failure; user prompted to restart

### Specific instances

| Date | Dispatch | Work done? | Consolidation msg? |
|---|---|---|---|
| 2026-07-04 | LocalLLaMA summarizer research subagent | yes | no (3 dispatches where 1 would have sufficed) |
| 2026-07-09 | dispatch_once 10 workers (mass spawn) | partial | no (workers crashed) |
| 2026-07-09 | Homepage sweep subagents | yes | partial (tail output only) |
| 2026-07-11 | joandrew 3-subagent batch (resolve-blocked + refresh-research + kanban-audit) | YES (files 25KB / 14KB / 66KB) | NO |

### Fix (the canonical pattern)

1. After dispatch returns `delegation_id`, IMMEDIATELY run `process(action='list')`
   to capture session_id
2. Set 5-min timer
3. If consolidation message missing after 5 min, run `process list` + `process poll <session_id>`
   to verify subagent state
4. If subagent is alive, wait
5. If subagent is done, **read output files from disk directly** — don't wait for the message

### Output file paths to check (per skill)

| Skill | Output path |
|---|---|
| `kanban-worker-lifecycle` | `~/.hermes/kanban/boards/<board>/workspaces/<task-id>/` |
| research subagents | project-specified output path |
| OCD sync | `~/Downloads/One-Cut-Deeper/` (git-tracked) |
| hermes-update-reconciler | `~/.hermes-state/snapshots/<date>/` |

### Citations in JOURNAL.md

- 2026-07-04 13:18 [tool:delegate_task] — "BEFORE re-dispatching a silent subagent, run process list"
- 2026-07-09 17:04 + 18:25 — mass-spawn antipattern
- 2026-07-11 03:00 — 3 subagent consolidation-hang instance

---

## Pattern B: Cross-Verify State Before Claiming

### When it fires

- Agent reports aggregate counts/state from a CLI tool output
- Without parallel direct query to the underlying data source
- The CLI may reconstruct from artifacts when live data is missing

### Specific instances

| Date | Claim | Reality |
|---|---|---|
| 2026-07-11 | "21 tasks on joandrew kanban, 16 done, 5 blocked" | `kanban.db` was empty (schema intact, 0 rows); `hermes kanban list` reconstructed from on-disk workspace artifacts |

### Fix

Before reporting aggregate state from any CLI:
1. Run a parallel direct query to the data source (e.g., `SELECT COUNT(*) FROM tasks`)
2. If CLI output ≠ DB row count, FLAG the claim as "reconstructed" not "live"
3. If the underlying DB is missing or empty, report THAT — not the CLI synthesis

### Data sources to cross-verify

| CLI | Data source |
|---|---|
| `hermes kanban list` | `sqlite3 ~/.hermes/kanban/boards/<board>/kanban.db "SELECT COUNT(*) FROM tasks"` |
| `hermes cron list` | `jq '.jobs | length' ~/.hermes/cron/jobs.json` |
| `hermes --version` | same — but verify with `hermes doctor` too |
| `hermes profile list` | `ls ~/.hermes/profiles/` |
| `git status` | (already authoritative) |

---

## Pattern C: Skill Pre-Load Skipped at Session Start (Pattern 7)

### When it fires

- Agent reads `mnemosyne_recall` but doesn't `skill_view` canonical skills
- Re-derives rules from memory + scratch instead of citing prior journal entries
- Same lesson re-learned across sessions

### Specific instances (2026-07)

| Date | Missed skill pre-load |
|---|---|
| 2026-07-02 | failures-journal, session-reflection (entry in JOURNAL.md) |
| 2026-07-04 | subagent-liveness-watchdog (mass-dispatch antipattern) |
| 2026-07-06 | hermes-llm-preflight (subagent HTTP 401) |
| 2026-07-07 | hermes-skill-loading-disciplines (memory 2026-07-07T18:50, importance 0.90) |
| 2026-07-11 | failures-journal, subagent-liveness-watchdog, hermes-session-open-inventory |

### Fix (the canonical pattern, 2026-06-30)

First 60 seconds of every session:
1. `skill_view(name="failures-journal")` — see recent failure patterns
2. `skill_view(name="subagent-liveness-watchdog")` — load process tracking discipline
3. `skill_view(name="hermes-session-open-inventory")` — verify current state
4. Check JOURNAL.md for entries from last 14 days whose "Rule for next time" is relevant
5. Cite relevant ones before doing the operation

### Anti-pattern detection

If you find yourself in the middle of an operation and realize you didn't
pre-load skills, STOP. Load them now. Cite what they would have warned you
about. Log to failures-journal.

---

## Frequency tally (as of 2026-07-11)

| Pattern | Count | Most recent |
|---|---|---|
| A. Subagent consolidation hang | 4 | 2026-07-11 |
| B. False state claims without cross-verify | 1 (today) | 2026-07-11 |
| C. Skill pre-load skipped | 5+ | 2026-07-11 |