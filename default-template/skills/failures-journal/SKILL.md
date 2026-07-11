---
name: failures-journal
uses: [hermes-session-open-inventory]
description: When an operation fails or a workflow hits a non-trivial mistake, log it to ~/.hermes/skills/failures-journal/JOURNAL.md (append a dated, structured entry). Check the journal at session start for prior related failures. Always log; never silently retry more than twice.

---# failures-journal

Required by SOUL.md and Pattern 7 (`agent-rule`): failures must be logged, not silently retried.

## When to log

Log a failure entry when **any** of:

- A tool/command returned a non-zero exit that the agent decided to work around (not propagate).
- The agent had to retry the same operation 3+ times to get it to land.
- The user corrected the agent's approach (correction memory candidate).
- A delegation/dispatch misfired (wrong profile, wrong context, dropped message).
- A cleanup/audit action was reversed by the user (means the rule was wrong).
- A skill's documented procedure didn't work and the agent had to improvise.
- **The agent itself caused a memory leak by re-encoding a stale fact as a new memory entry (NEW 2026-07-09).** Pattern: a user says "X is wrong / orphaned / don't memorize" and the agent reflexively writes a Mnemosyne note restating the absence. That re-encodes the very stale fact the user wanted forgotten. The right move is `mnemosyne_invalidate(<old_id>)` and write NO replacement. If the agent DID write a re-encoded note, log it to the journal as a self-correction entry and invalidate it on the next turn (the next session can sweep with `mnemosyne_recall(query="<stale fact key phrase>")` and invalidate every match).

**Do NOT log:** single transient errors that retried cleanly. The journal is for *patterns*, not noise.

## Entry format (append to JOURNAL.md)

```markdown
## YYYY-MM-DD HH:MM | <one-line title>

**Context:** <what I was doing, 1 line>
**What went wrong:** <the specific failure, 1-2 lines>
**Root cause:** <why, 1-2 lines>
**Fix:** <what I did, 1-2 lines>
**Rule for next time:** <the durable lesson, 1 line — this is what makes the journal valuable>
```

Keep entries **≤ 8 lines**. The rule is the load-bearing part — it's what gets re-read at session start.

## Verified recurring patterns on this host (2026-07-11)

These have each happened **3+ times** on this host and must be cited at session start:

### Pattern A — "Treat silence as failure" (2026-07-04 + 2026-07-11, 4th time)

**Symptom:** Dispatched a subagent (via `delegate_task` or `terminal(background=true)`);
waited for the consolidation message that should re-enter the parent conversation;
after a few minutes of silence **declared failure** and either re-dispatched
or prompted the user to restart.

**Root cause:** Subagent WORK often completes successfully (files written,
state mutated) but the **consolidation message** can be delayed, dropped,
or stuck in the framework's delivery queue. The agent's failure mode is
treating "no message yet" as "didn't work" without checking the actual evidence.

**Fix:** Before declaring any silent subagent "failed":
1. Run `process(action='list')` — if session_id is present and state='running', it's alive; wait.
2. Run `process(action='poll', session_id=<sid>, timeout=10)` — poll output delta.
3. Read the known output path on disk directly — if files exist with recent mtime, the work happened.
4. Apply the 30-second second-look rule (see `subagent-liveness-watchdog` skill).

**Specific incident 2026-07-11:** 3 subagents dispatched (deleg_9dfb8687) wrote 25KB / 14KB / 66KB output files within 4-6 minutes. Consolidation message did NOT arrive. Agent initially treated as failure. Files existed on disk the entire time.

### Pattern B — "Cross-verify state before claiming" (2026-07-11)

**Symptom:** Agent reports aggregate count from a single CLI tool output
(e.g., "21 tasks on the kanban") without cross-verifying against the
underlying data source.

**Root cause:** The `hermes kanban list` CLI may return **artifact-reconstructed
data** when the live kanban SQLite DB has been emptied or migrated. Trusting
the CLI output without a parallel DB query produces false claims that look
authoritative.

**Fix:** Before reporting aggregate state from any CLI:
1. Run a parallel direct query to the data source (e.g., `SELECT COUNT(*) FROM tasks`)
2. If CLI output ≠ DB row count, FLAG the claim as "reconstructed" not "live"
3. If the underlying DB is missing or empty, report THAT — not the CLI synthesis

**Specific incident 2026-07-11:** `~/.hermes/kanban/boards/joandrew/kanban.db` was
empty (schema intact, tables empty); `hermes kanban list` reconstructed 21 tasks
from on-disk workspace artifacts. Agent claimed "16 done, 5 blocked" — false.

### Pattern C — "Skill pre-load skipped at session start" (Pattern 7 from 2026-06-30)

**Symptom:** Agent reads `memory` at session start but doesn't `skill_view` the
canonical skills (`failures-journal`, `hermes-session-open-inventory`,
`subagent-liveness-watchdog`, etc.). Re-derives rules from scratch instead of
citing prior journal entries.

**Root cause:** Memory lookup ≠ skill pre-load. The skill discipline is:
load skill, see what prior sessions logged, cite those entries BEFORE acting.

**Fix:** First 60 seconds of every session:
1. `skill_view(name="failures-journal")` — see recent failure patterns
2. `skill_view(name="subagent-liveness-watchdog")` — load process tracking discipline
3. `skill_view(name="hermes-session-open-inventory")` — verify current state
4. Check JOURNAL.md for entries from the last 14 days whose "Rule for next time" is relevant
5. Cite relevant ones before doing the operation

**Frequency:** Bitten this user at least 5x in 2026-07 alone (memory 2026-07-07T18:50, importance 0.90). Memory entry says: "agent keeps learning the same lessons but treating each re-discovery as fresh."

For the full catalog of recurring patterns with verified specific instances,
see `references/recurring-patterns.md` (4-time subagent hang, cross-verify
state claims, skill pre-load skip).

## At session start

Scan JOURNAL.md for entries from the last 14 days whose `Rule for next time` line is relevant to today's task. Cite them by date if you find one matching.

## Why this exists

The skill discipline says: when something fails, log it before retrying. Most agents (and most past sessions on this machine) skip the log and try again 3 times — turning a 1-minute fix into 5 minutes. The journal makes the failure visible to the next session, which is the only thing that actually breaks the loop.
