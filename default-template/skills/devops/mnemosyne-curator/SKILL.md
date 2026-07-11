---
name: mnemosyne-curator
uses: [mnemosyne-memory]
description: "Use when running the weekly Mnemosyne memory hygiene cron, when memory counts feel bloated, or when the user asks to clean up memories, mark stale memories, or consolidate working memory. Marks stale memories, compresses working to episodic, surfaces forgotten candidates. ALSO use when the user says 'forget X / remove any reference to orphan Y from memories' (the user-forget workflow — NEW 2026-07-09). Also load for any 'X is gone / wrong / orphaned' cleanup that pairs Mnemosyne invalidation with file-system soft-delete."
version: 1.5.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, mnemosyne, curator, cron, hygiene, consolidation, graph, linking, user-forget, orphan-cleanup]
    category: devops
    related_skills: [domain-recall, hermes-skill-authoring-gotchas, mnemosyne, failures-journal, filesystem-audit-and-consolidate, hermes-soft-delete-discipline]
    config: []
    changelog:
      - "1.5.0 (2026-07-09): Added 'User-forget workflow' section — the 5-step interactive procedure for when the user says 'forget X / remove any references of orphan Y from memories / X is gone now'. Pairs with Pitfall #17 (don't re-encode orphans in new memory) and externalizes the procedure from the implicit reflex. Trigger phrases: 'forget X', 'X is orphaned / gone / dead', 'remove any references of X', 'refactor said files unless deemed not useful remove them'. Cost of NOT using: the user flagged this as the highest-cost pollution pattern after 4 iterations on a single orphan. Pairs with `filesystem-audit-and-consolidate` (file cleanup) and `hermes-soft-delete-discipline` (trash convention). Source: 2026-07-09 user verbatim 'remove any references of orphan from memories and refactor said files unless deemed not useful remove them'."
      - "1.4.0 (2026-07-09): Added Pitfall #17 — don't re-encode orphans in new memory. Captures the 4-session-stale-fact leak pattern (AppData/Local/hermes orphan replayed 4x). 4-step rule + telltale diagnostic. Pairs with Pitfall #15 (don't remember_canonical a contradicted fact). Source: user verbatim 'this is the fourth time in multiple sessions u layed out that AppData/Local/hermes is orphaned meaning u truly never deleted it, if u want to forget it just dont even try to memorize it after deleting it that its orphaned to truly forget it.'"
      - "1.3.0 (2026-07-07): Added Stage 5 (Linking) + companion `scripts/emit_supersede_edges.py`. Source: 2026-07-07 session."
---

# Mnemosyne Curator

**Pattern:** Weekly memory hygiene pass that runs unattended on Sunday 03:00 local time. Three stages: (1) snapshot state, (2) mark stale candidates for invalidation, (3) compress working → episodic, (4) surface anything flagged for user review. Reversible via `mnemosyne_validate(action='attest')`.

**Why:** Mnemosyne is append-only by default — every `mnemosyne_remember` adds to working memory, and unconsolidated working memory grows forever. Without curation, recall gets noisy, episodic summaries drift, and the user ends up with thousands of low-signal memories that drown the high-signal ones. Daily `mnemosyne_sleep` consolidates within a session; this skill is the **weekly cross-session sweep** that handles inter-session staleness, expiry, and forgotten candidates.

This skill does not duplicate `daily-mnemosyne-sleep`. That cron runs `mnemosyne_sleep(all_sessions=False)` at 04:00 every day for the current session. This curator runs `mnemosyne_sleep(all_sessions=True, force=False)` once a week at 03:00 Sunday, plus the staleness and review stages.

## When to Use

- The cron entry `mnemosyne-curator` fires (Sunday 03:00 local) and attached skill is loaded.
- The user says "clean up my memories", "mark stale memories", "what memories can I delete?", or "consolidate working memory".
- The user says "forget X", "remove any reference to orphan Y from memories", "X is gone / wrong / orphaned", or asks to "refactor files" alongside a memory cleanup. **Use the user-forget workflow (NEW 2026-07-09, this user) below** — different from the unattended cron.
- `mnemosyne_stats()` shows working > 2000 with unconsolidated > 500 (memory bloat).
- The user asks "what have I forgotten?" — surface candidates via recall + low-importance filter.

**Don't use for:**

- Single-session nightly consolidation. That's `daily-mnemosyne-sleep`. Two crons overlap if you point this skill at it.
- Hard-deleting canonical slots (identity facts, user preferences, source-of-truth memories). See Pitfalls.
- Forensic recall. Use `mnemosyne_recall(query=...)` directly, not the curator.

## Curate Policy

These thresholds are the curator's defaults. They are tuned for a profile that has run Mnemosyne continuously for months (1k-3k working memories) and where daily consolidation has kept unconsolidated count low.

| Stage | Threshold | Behavior |
| --- | --- | --- |
| **Staleness (invalidate candidates)** | `importance < 0.3` AND `age > 30 days` AND `valid_until` empty | Recall + filter, surface to user for sign-off. **Never auto-invalidate below 0.1 importance without explicit user OK.** |
| **Compression (working → episodic)** | `mnemosyne_sleep(all_sessions=True, force=False)` | Default age threshold is conservative; works on top of `daily-mnemosyne-sleep`. |
| **Forgotten candidates** | `importance < 0.2` AND `age > 60 days` AND no recall hits in last 30 days | Surface as "delete candidates" but do **not** auto-delete. User picks. |
| **Never touch** | `importance >= 0.7`, OR `source in {identity, preference, fact}` | Skip. Canonical slots. |

**Grace period:** 30 days. A memory under 30 days old is treated as still-active context regardless of importance, because session-scoped memories are written with low importance on purpose.

**Why three stages not one:** consolidation is safe and reversible (working memories are summarized, originals get a `consolidated` flag, episodic gains an entry). Invalidation is one-way (memory_id is marked, replacement_id is optional). Deletion is one-way and unrecoverable. Each stage needs a different signal-to-noise ratio and a different blast radius.

## Step-by-Step Procedure

Run in this exact order. Do not skip the snapshot — it is the only way to roll back.

**Stage 0 — Snapshot.** `mnemosyne_stats()` then `mnemosyne_diagnose(repair_vec_working=False)`. Record `working.total`, `working.unconsolidated`, `episodic.total`. If `unconsolidated == 0`, emit silent output and exit. Completion: stats captured, `unconsolidated > 0`, no diagnose blockers.

**Stage 1 — Compress.** `mnemosyne_sleep(all_sessions=True, force=False)`. Never `force=True` on the curator — that bypasses the age threshold and consolidates fresh session context. After sleep, `mnemosyne_stats()` again; record delta in `working.consolidated`. Completion: post-sleep stats captured.

**Stage 2 — Staleness candidates (read-only).** Enumerate low-importance + old memories. The `scripts/find_stale.py` companion (below) handles this via SQL. In-agent fallback:

```
mnemosyne_recall(query="stale low-importance memory", limit=20, temporal_weight=0.0, vec_weight=0.3, fts_weight=0.5, importance_weight=0.2)
```

Filter client-side: `importance < 0.3` AND `age > 30 days` AND `valid_until` empty. Render top 10 with memory_id, content preview (first 80 chars), importance, age. **No `mnemosyne_invalidate` calls — surface only.**

**Stage 3 — Forgotten candidates (delete-only-with-user-OK).** Same recall shape, tighter filter: `importance < 0.2` AND `age > 60 days` AND no recall hits in last 30 days (fall back to age > 90 days if recall count is unavailable). Surface as recommendations; the curator never calls `mnemosyne_forget` without explicit per-memory user approval.

**Stage 4 — Attestation (optional).** For high-importance memories (`importance >= 0.7`), run `mnemosyne_recall(query="user preferences identity facts", limit=20, importance_weight=0.5)` and attest each via `mnemosyne_validate(memory_id=<id>, action="attest", validator="mnemosyne-curator")`. Keeps the validator ring buffer fresh. The curator only attests — never updates or invalidates through `mnemosyne_validate`.

**Stage 5 — Linking (NEW 2026-07-07, opt-in).** After user sign-off on Stage 2 invalidations, emit one `mnemosyne_graph_link` edge per superseded pair so the relation is traversable, not just stale-marked. Background: the user asked "relation between memory should be merged after review, and validation" — without an explicit edge, recall can still surface the obsoleted fact at full hybrid score. The graph is what makes the merge durable. Procedure:

1. For each `(obsolete_id, replacement_id)` pair the user approved in Stage 2:
   ```
   mnemosyne_graph_link(
     source_id=<obsolete_id>,
     target_id=<replacement_id>,
     relationship="supersedes",
     weight=0.9
   )
   ```
2. For canonical-slot supersedes, use `mnemosyne_remember_canonical(category, name, body)` to the same slot — the wrapper handles v1→v2 versioning. Do NOT also call `graph_link` for canonical slots; the version chain IS the relation.
3. For orphaned invalidations (no replacement), emit a self-edge so the audit trail is queryable:
   ```
   mnemosyne_graph_link(
     source_id=<obsolete_id>,
     target_id=<obsolete_id>,  # self-edge
     relationship="orphaned",
     weight=0.5
   )
   ```
4. After linking, verify with `mnemosyne_graph_query(seed_memory_id=<canon>, edge_type="supersedes", max_hops=2)` and confirm the obsolete id appears in the result set.

**Why a separate stage (not bundled into Stage 2):** Stage 2 is read-only and runs unattended. Linking is a write, and the user must approve WHICH edges get linked. Two separate gates.

**Why the wrapper not the library:** `mnemosyne_graph_link` is registered by the Hermes plugin wrapper at `~/.hermes/plugins/mnemosyne/__init__.py:_handle_graph_link` (line ~1683). The Mnemosyne library itself (`pip install mnemosyne-memory` v3.11.1) has NO graph API in its public surface — 14 lazy exports, all flat fact-store primitives. If the wrapper is missing, fall back to direct SQLite `INSERT INTO graph_edges (source, target, edge_type, weight, timestamp) VALUES (?, ?, 'supersedes', 0.9, ?)`. Same data, no LLM. **Never claim a function exists because the skill doc mentions it — verify against `dir(mnemosyne)` first** (see Pitfall #16).

**Reversibility:** `graph_edges` rows can be hard-deleted (`DELETE FROM graph_edges WHERE id = ?`) if a link is wrong. No audit table; pair with a `mnemosyne_remember(content="edge audit: <src> supersedes <tgt> 2026-07-07", importance=0.4, source="linker-audit")` write if you want history.

## Cron Wiring

The cron entry lives in `~/.hermes/cron/jobs.json`. Two ways to add it.

**Option A — `cronjob` CLI (preferred):** wraps the JSON file with proper nested `schedule.kind/expr/display` and a generated id.

```bash
cronjob action='create' \
  name='mnemosyne-curator' \
  schedule='0 3 * * 0' \
  prompt='Run the mnemosyne-curator procedure. See skill ~/.hermes/skills/devops/mnemosyne-curator/SKILL.md' \
  skills='["devops/mnemosyne-curator"]' \
  no_agent=false \
  deliver='local' \
  enabled=true
```

**Option B — Direct JSON patch:** append a new entry to the `jobs` array using the same nested `schedule` shape as existing entries. The minimal payload:

```json
{
  "name": "mnemosyne-curator",
  "prompt": "Run the mnemosyne-curator procedure. See skill ~/.hermes/skills/devops/mnemosyne-curator/SKILL.md",
  "skills": ["devops/mnemosyne-curator"],
  "no_agent": false,
  "schedule": { "kind": "cron", "expr": "0 3 * * 0", "display": "0 3 * * 0" },
  "schedule_display": "0 3 * * 0",
  "enabled": true,
  "state": "scheduled",
  "deliver": "local"
}
```

Bump `updated_at` to the current ISO 8601 timestamp when patching directly — `cronjob action='list'` sorts by this field.

**Schedule:** `0 3 * * 0` = 03:00 every Sunday. Sits 1 hour before `daily-mnemosyne-sleep` (04:00 daily) so the curator can run first and produce the report that lands at the same local delivery target.

**Deliver `local`:** the curator writes its output to the cron's local delivery channel (default `~/.hermes/cron/output/`). It does **not** push to `origin` (channel push). The weekly curator is informational — the user reads it when they next open Hermes, not as a push notification.

**Skills attached:** `devops/mnemosyne-curator` — auto-loads this SKILL.md when the cron fires. Without this attachment, the cron prompt runs without curator context and would improvise — do not rely on the prompt alone.

**`no_agent: false`:** the curator needs the full tool surface (`mnemosyne_*` model tools, `terminal` for SQL helpers, `file_tools` for reading logs). Setting `no_agent: true` would strip those and the curator would degrade to a passive prompt.

## Output Format

Three tiers, picked by the magnitude of what changed:

### Silent — no curation needed

If Stage 0 shows `working.unconsolidated == 0` and `episodic.total` is unchanged from last week, the curator emits exactly one line:

```
mnemosyne-curator: no-op (working unconsolidated=0, episodic=131)
```

The cron should still mark success. Silent output is **not** a failure.

### Minor — small consolidation, no candidates

If sleep ran but Stage 2 and 3 produced zero candidates, emit a one-line summary:

```
mnemosyne-curator: consolidated=42 (working 2011→1969), episodic 131→131, 0 stale, 0 forgotten
```

This is the typical weekly output once the memory bloat is under control.

### Loud — candidates to review

If Stage 2 or 3 produced any candidates, emit the full structured report:

```
mnemosyne-curator: weekly report
  compression: working 2011→1847, episodic 131→138, +164 consolidated
  stale candidates (10):
    m_3f8a — "user prefers tabs over spaces in python" — importance 0.2 — age 47d
    m_7b21 — "api endpoint for foo service is at /v1" — importance 0.15 — age 89d
    ...
  forgotten candidates (5):
    m_a112 — "explored hermes-cli flag X" — importance 0.1 — age 73d
    ...
  action: review stale list and forgotten list; reply with memory_ids to invalidate or forget
```

The cron delivers this report to `local`. The user reads it at next session start.

## Reversal Procedure

Two reverse paths, depending on what the curator did:

**Reversing an attestation (Stage 4).** `mnemosyne_validate(action="attest")` is non-destructive — it appends to the 3-entry ring buffer. To "un-attest," call again with `validator="user-override"`; the curator's entry stays in the ring buffer but the user becomes the most recent attester.

**Reversing an invalidation (Stage 2 with user OK).** The curator calls `mnemosyne_invalidate(memory_id=<id>, replacement_id="")` only after explicit user approval. To reverse, recall what the replacement memory_id should be, then call `mnemosyne_invalidate(memory_id=<replacement_id>, replacement_id="<original_id>")` to chain them back. If there was no replacement (memory invalidated as orphaned), the original is gone from active recall — recall `query="<original content>"` to find the episodic summary that absorbed it; that summary is the post-recovery canonical state.

**Recovering from a deletion (Stage 3).** `mnemosyne_forget` is hard delete. Recovery in order of preference:

1. Check `~/.hermes/mnemosyne/data/` for an export JSON from the last 30 days — `mnemosyne_import` is idempotent.
2. Check episodic memory for the summary that absorbed the working memory before deletion.
3. Re-derive and `mnemosyne_remember(content=..., importance=0.7, source="recovered", metadata={"recovered_from": "<original_id>"})`.

Surface this recovery procedure in the curator's weekly report whenever any deletion ran. A user who doesn't know `mnemosyne_forget` is irreversible will not ask the right recovery questions.

## Common Pitfalls

1. **Auto-invalidating without user approval.** Stages 2-3 surface candidates and wait for user confirmation. `mnemosyne_invalidate` is a manual override from the curator, never the default. `daily-mnemosyne-sleep` is safe unattended because sleep summarizes; the curator must preserve that property.

2. **Forgetting the daily cron.** `daily-mnemosyne-sleep` runs 04:00 daily. The curator at 03:00 Sunday runs before it. Sleep is idempotent so overlap is harmless, but if you want strict ordering, set the daily to `0 4 * * 1-6` (Mon-Sat only).

3. **Using `force=True` on `mnemosyne_sleep` to "clean harder."** This bypasses the age threshold and consolidates fresh working memories into episodic — destroys per-session rolling context. Always `force=False`.

4. **Treating `importance < 0.3` as "delete me."** Importance is a recall weight, not a correctness signal. Cross-check with recall count before any action.

5. **Touching canonical slots.** Memories with `source in {identity, preference, fact}` and `importance >= 0.7` are load-bearing. Surface for review; never auto-invalidate.

6. **`deliver: "origin"`** turns the curator into a 03:00 Sunday push notification. Use `deliver: "local"`.

7. **`no_agent: true`** strips the `mnemosyne_*` tools and `terminal`. The prompt becomes a passive summary. Keep `no_agent: false`.

8. **Cross-profile bleed.** Skills load per-session, not per-cron-fire. Attach the skill in the profile that owns the cron, or the cron prompt runs without curator context.

9. **Forgetting to bump `updated_at`.** When patching `jobs.json` directly, set the current ISO 8601 timestamp — `cronjob action='list'` sorts by it.

10. **Surfacing candidates without memory_ids.** The user cannot act on "memory about tabs" — they need `m_3f8a` to tell the curator which one to invalidate.

11. **Skill on disk ≠ cron is registered (NEW 2026-07-03, highest leverage).** The curator SKILL.md existing at `~/.hermes/skills/devops/mnemosyne-curator/SKILL.md` does NOT mean the curator is firing. There are three distinct states: (a) skill + companion `scripts/find_stale.py` on disk, (b) cron entry in `hermes cron list`, (c) cron entry `enabled: true` with `Last run:` recent. The 2026-07-03 inventory found this skill + companion fully built but the curator cron entry ALSO registered — yet `hermes cron list` rendered only 3 of 6 entries (truncated table output). The truth was in `cat ~/.hermes/cron/jobs.json`. **Mandatory pre-flight before assuming any curator behavior exists:**

    ```bash
    # Convenience command — may be truncated. Cat the source-of-truth:
    cat ~/.hermes/cron/jobs.json | python -m json.tool | grep -E '"name"|"enabled"|"last_run_at"' | head -30
    ```

    The same three-state check applies to ANY domain-specific watchdog (comfyui, sd-model-merge, hermes-internal). Do not assume a skill's presence means its automation is alive. Particularly relevant for this skill because: (i) the user's whole Mnemosyne-corpus health depends on it running weekly, and (ii) the failure mode is silent — Mnemosyne grows fine without it, it just grows forever.

12. **`always_load` vs cron's `skills=[...]` (NEW 2026-07-03).** A common confusion: "is the curator loaded?" The answer depends on what you mean. The cron entry's `skills=["devops/mnemosyne-curator"]` attachment loads the skill at cron-fire time — that is how the curator runs on Sunday 03:00. `~/.hermes/config.yaml` `always_load` controls per-session skill loading for interactive chat — and that list does NOT need the curator (or any other periodic-task skill) on it. **Adding `mnemosyne-curator` to `always_load` would waste ~2KB per session on a skill that fires once a week.** Don't.

13. **Two load paths, one skill:** (a) **Cron path** — `cronjob action='create' skills='["devops/mnemosyne-curator"]'` loads at fire time. Use this for periodic / unattended work. (b) **Interactive path** — user asks "clean up my memories" → agent loads via `skill_view(name="mnemosyne-curator")` on demand. Both paths work; use the one matching the trigger.

14. **If ALL cron jobs show `last_run_at: never`, the cron SUBSYSTEM is broken, not your job (NEW 2026-07-06, this user).** Pitfall #11 above catches the case where one specific job (curator) is missing or disabled. But the 2026-07-06 inventory found the worse case: `~/.hermes/cron/jobs.json` had 6 enabled jobs (`monthly-model-research`, `weekly-knowledge-digest`, `one-cut-deeper-sync`, `daily-mnemosyne-sleep`, `hermes-update-watchdog`, `mnemosyne-curator`) and **ALL 6 had `last_run_at: never`**. That's not a missing job — that's the cron daemon not firing at all. Re-registering this curator job won't help; the same fate will befall it within 24h.
    Diagnostic ladder:
    1. `cat ~/.hermes/cron/jobs.json | python -m json.tool` — count jobs, confirm all are `enabled: true` and have a `schedule` block.
    2. `hermes cron list` — verify CLI sees the same jobs.
    3. `ls -la ~/.hermes/cron/` — look for `ticker_heartbeat`, `ticker_last_success`, `.tick.lock`. If `ticker_heartbeat` mtime is older than ~5 minutes, the ticker isn't running.
    4. `hermes cron status` / `hermes cron tick --once` — manual tick to verify the runner works at all.
    5. If manual tick succeeds but scheduled tick never fires, the cron scheduler itself is the problem (e.g., the scheduler process is not running as a long-lived service; the desktop app owns the ticker and it dies when the desktop closes).
    6. Recovery: ensure the ticker runs as a long-lived process (e.g., via `hermes serve` or a Windows Task Scheduler entry that survives logout). Don't waste time fixing individual jobs until the runner is alive.
    This is distinct from pitfall #11: #11 is "this specific job is missing." #14 is "the whole cron subsystem is dark." Same fix shape (re-register), but the root cause is one level deeper, and the re-registration will fail silently unless the underlying runner is fixed first.

15. **Do not `mnemosyne_remember_canonical` a fact the user has just contradicted (NEW 2026-07-06, this user — highest-cost pollution pitfall).** The curator runs because high-signal memories are durable. The trap: when the user dismisses a long-standing canon with "invalidate that" / "delete that" / "no, that's wrong now", the agent is tempted to (a) confirm the dismissal by `remember_canonical`ing a NEW contradictory canon, (b) defend the existing canon, or (c) call `mnemosyne_validate(invalidate)` on the old one AND immediately add a fresh one. All three are wrong. The correct sequence:

    1. **Invalidate first, write second.** The user-visible action is removal, not replacement. The old canon stays in Mnemosyne as `invalidated` until the next sleep/curator pass; that's correct, not a leak.
    2. **Don't auto-promote the user's correction to canon.** A user saying "X is wrong, it's Y now" is information, not a request to make Y load-bearing for future sessions. The next time the user wants to recall the topic, surface both as candidates and let them confirm. Auto-promotion is the failure mode that pollutes recall with contradictions the user has to manually filter out.
    3. **Confirm only after the user has been told what's about to change.** "I'll invalidate m_abc and add the corrected version as mnemosyne_remember_canonical" + a pause for "go ahead" beats firing both calls in one turn. A 2-call sequence that fires without pause is the pollution recipe.
    4. **The agent's own certainty is not a license.** The 2026-07-06 SD-Image-Research cleanup found the agent `mnemosyne_remember_canonical`ing a "Notes/Hermes canonical" entry as if confirming a fact the user had just told it to dismantle. The agent was retroactively ratifying the canon it should have been disassembling. This is silent and self-reinforcing — the next session's recall surfaces the agent's own wrong confidence as ground truth.
    Diagnostic: if a `mnemosyne_remember_canonical` call in the same turn ALSO has the user explicitly saying "delete that" / "invalidate that" / "no, that's wrong now" / "not anymore" / "remove that", the call is wrong. The fix is to drop the call and only invalidate; the next sleep/curator pass handles the rest.

16. **Verify the API surface before citing it as "available" (NEW 2026-07-07, this user — caused the 2-bug repetition pattern to grow a 3rd).** The `mnemosyne-memory` skill doc references many `mnemosyne_*` tool names that are actually registered by the **Hermes plugin wrapper** at `~/.hermes/plugins/mnemosyne/__init__.py`, not by the upstream Mnemosyne library. The library itself (`mnemosyne-memory` PyPI, v3.11.1) exposes only 14 lazy symbols: `Mnemosyne`, `remember`, `recall`, `get_context`, `get_stats`, `get`, `forget`, `update`, `reclaim_orphans`, `SyncEngine`, `SyncEvent`, `SyncEncryption`, `ConflictResolution`, `run_sync_server`, plus `run_mcp_server` if `mcp` is installed. **No `graph_link`, no `graph_query`, no `triple_add`, no `triple_query`, no `invalidate`, no `validate` in the library.** Those are all in the wrapper. The data tables (`graph_edges`, `triples`) DO exist in the DB but are written by the wrapper, not the library's `sleep` cycle. Verification recipe before citing any Mnemosyne function in chat:

   ```python
   import mnemosyne
   print(mnemosyne.__version__)                # 3.7.0+ = real
   print(sorted(a for a in dir(mnemosyne) if not a.startswith("_")))
   # for graph/triple schemas, also check the wrapper:
   grep -nE "GRAPH_LINK_SCHEMA|TRIPLE_ADD_SCHEMA|_handle_graph_link" \
     ~/.hermes/plugins/mnemosyne/__init__.py
   ```

   **The 2026-07-07 failure:** the agent told the user "I can emit `mnemosyne_graph_link` edges" as if it were a Mnemosyne primitive. The user asked for verification; the agent then had to backtrack. The fix is to run the verification **before** the citation, not after the user catches it. This is the verify-then-cite pattern, not the cite-then-verify pattern. **If you cannot run the verification in the same turn, say "I'm not certain whether this is a library or wrapper function; let me check" — never bluff.**

   Diagnostic: if a `mnemosyne_*` name appears in the `mnemosyne-memory` SKILL.md, the user-visible `mnemosyne-tools` list, AND in `plugins/mnemosyne/tools.py` schemas, it is wrapper-side. If it appears in `mnemosyne/__init__.py` `_lazy_exports`, it is library-side. The two are different surfaces; conflating them is the failure mode.

17. **Don't re-encode orphans in new memory (NEW 2026-07-09, this user — the 4-session-stale-fact leak).** The reflex when the user says "X is gone / wrong / orphaned" is to write a new memory entry like "X is orphaned (supersedes 2026-07-01, 2026-07-03, 2026-07-05, 2026-07-06)" — the user has been burned by this exact pattern 4 times in a row on the "AppData/Local/hermes is orphaned" fact. Each iteration of "X is wrong" + "I wrote a new memory confirming X is wrong" leaves the orphan **more durable in recall** than before, not less. The leak lives in the entry, not the agent's behavior.

    **The 4-step rule (capture, don't perpetuate):**

    1. **Invalidate the stale memory** via `mnemosyne_invalidate(memory_id=<old_id>)`. This removes the entry from active recall. One call, no replacement.
    2. **Do NOT write a replacement that mentions the orphan.** "Hermes home = ~/.hermes" is a clean forward-looking rule. "Hermes home = ~/.hermes (not AppData/Local/hermes, which is orphaned)" leaks the orphan back into recall.
    3. **If the orphan fact matters for safety, capture it as a forward-looking agent-rule, not as a fact about an orphan state.** "Treat AppData/Local/hermes paths as non-existent in `path.exists()` checks" is durable. "AppData/Local/hermes is an orphan" ages into the same pollution.
    4. **The diagnostic for "is this re-encoding an orphan?":** before saving a new memory, check the content for these telltales — "X is no longer", "Y has been replaced by Z", "old path W does not exist", "is orphaned", "is dead", "supersedes prior". If ANY of these appear and the new memory doesn't add a forward-looking rule, **drop the new memory and just invalidate the old one**.

    **Concrete instance on this host (2026-07-09):** "AppData/Local/hermes is orphaned, do not write there" appeared in 4 separate memory entries across 4 sessions. The correct fix was: invalidate all 4 + write ONE new memory with the forward-looking rule "Hermes home is `~/.hermes` (C:\Users\somew\.hermes)"; never re-mention AppData. The new memory's importance should be ≥ 0.7 so it dominates recall for the topic, but the orphan should not appear anywhere in the new entry's body.

    **Diagnostic check the curator can run:** for any new `mnemosyne_remember` or `mnemosyne_validate(action='update')` call in the same turn as a `mnemosyne_invalidate`, search the new content for the same 4-5 keywords as the invalidated entry. If they overlap by >30%, the new entry is re-encoding the orphan — drop it and only invalidate. The cost of dropping is one fewer durable fact; the cost of keeping is the orphan persists in recall forever.

    **Pair with Pitfall #15 (don't `remember_canonical` a contradicted fact).** #15 covers the "auto-promote user's correction to canon" trap. This pitfall (#17) covers the "auto-rewrite the correction as a memory about the prior wrongness" trap — same family (auto-canonization of user corrections), different failure surface. Both are part of the broader Pattern: **the user dismissing a fact is information, not a request to memorize the dismissal.**

## User-forget workflow (NEW 2026-07-09, this user)

When the user says "forget X / remove any references of orphan Y from memories / X is gone now," do NOT improvise. The reflex of writing "X is gone (supersedes Y, Z)" memory entries is Pitfall #17. The CORRECT interactive procedure is a 5-step audit that pairs Mnemosyne invalidation with file-system cleanup:

**Step 1 — Load the canonical rule.** Before invalidating anything, recall what the FORWARD-LOOKING rule is that should remain. Example: "remove any references of `~/Documents/hemes-research/` from memories" — load the canonical STORAGE RULE (memory `8ec990ca844a8dfd`) which says "NEITHER `~/Documents/hemes-research/` NOR `~/Documents/hermes-research/` is canonical. CANONICAL locations are: (1) CWD, (2) Obsidian vault." Verify the canonical rule is still importable — `mnemosyne_recall(query="hermes research storage canonical location Documents home")` should surface it.

**Step 2 — Find the orphan-path re-encoding entries.** Search for memories that mention the orphan path/fact. Pattern: `mnemosyne_recall(query="<orphan path/fact>", limit=10)`. Each result that contains "X is gone / wrong / orphaned / no longer / replaced by / supersedes prior" alongside the orphan is a candidate for invalidation. Distinguish three classes:
- **Class A: stale-fact re-encoding** ("X is orphaned, do not write there") — INVALIDATE. Per Pitfall #17.
- **Class B: forward-looking rule** ("Treat AppData/Local/hermes paths as non-existent in path.exists() checks") — KEEP. This is durable and useful.
- **Class C: factual reference** ("Hermes home = ~/.hermes" without mentioning the orphan) — KEEP. This is correct, just stale-tagged if you want.

**Step 3 — Invalidate each Class A entry.** One `mnemosyne_invalidate(memory_id=<id>)` per entry. NO replacement writes. The user-visible action is removal, not replacement. If a replacement IS warranted (the user explicitly asks for a new rule), do it in a SEPARATE `mnemosyne_remember` call AFTER all invalidations are confirmed.

**Step 4 — Verify via recall.** After invalidating, run `mnemosyne_recall(query="<orphan path/fact>", limit=5)` again. The invalidated entries should NOT surface (or surface at very low scores). The Class B/C forward-looking rules SHOULD surface. If the canonical rule from Step 1 is gone, STOP — you over-invalidated, restore via `mnemosyne_validate(action="attest", ...)` on the right memory_id after re-deriving it from episodic summary.

**Step 5 — File-system cleanup (paired with the memory work).** Per `hermes-soft-delete-discipline`, NEVER hard-delete user files. Use `~/.hermes/trash/<date>-<fix-name>/` snapshot pattern:
- Move files to trash with a descriptive subfolder name (e.g. `~/.hermes/trash/2026-07-09-home-audit/bin-snapshot/`, `downloads-snapshot/`, `check-snapshot/`).
- Use `mv` (not `rm`) — fully reversible for 30+ days.
- Keep the canonical canonical copies in their canonical locations (move hermes scripts to `~/.hermes/bin/`, research reports to `~/.hermes/docs/`, NOT to the trash).
- Empty dirs are `rmdir`-safe (the `rmdir` syscall refuses non-empty dirs as a safety net).

**Trigger phrases for this workflow:**
- "forget X / remove X from memory"
- "X is gone / wrong / orphaned / no longer"
- "remove any references of X from memories"
- "X is dead, clean it up"
- "refactor said files unless deemed not useful remove them" (user verbatim, 2026-07-09)
- "clean up my home dir / audit C:\Users\<user>"

**Cost of NOT using this workflow:** Pitfall #17 fires. The leak lives in the memory entry, not the agent's behavior. Each time you re-encode an orphan, the user has to clean it up again. After 4 iterations on a single orphan ("AppData/Local/hermes is orphaned" appeared in 4 separate memory entries across 4 sessions), the user explicitly flagged this as the highest-cost pollution pattern. **The 5-step workflow above is the durable fix.** Pairs with `filesystem-audit-and-consolidate` for the file-system half and `hermes-soft-delete-discipline` for the trash convention.

## Verification Checklist

- [ ] `mnemosyne_stats()` ran before and after sleep; delta recorded
- [ ] `mnemosyne_diagnose()` returned no blocking errors
- [ ] `mnemosyne_sleep(all_sessions=True, force=False)` ran (never `force=True`)
- [ ] No `mnemosyne_invalidate` calls executed without explicit user approval
- [ ] No `mnemosyne_forget` calls executed by the curator (delete candidates only surfaced)
- [ ] Output fits silent / minor / loud tier and was delivered to `local`
- [ ] If loud: every candidate line includes memory_id, content preview, importance, age
- [ ] Cron entry in `~/.hermes/cron/jobs.json` has `enabled: true` and `deliver: "local"`
- [ ] `cronjob action='list'` shows the entry with `next_run_at` populated for next Sunday 03:00
- [ ] If Stage 5 ran: every `mnemosyne_graph_link` call returned `status: "linked"`, audit JSON archived to `~/.hermes/mnemosyne/curator/links-<ISO-date>.json`, and a follow-up `mnemosyne_graph_query(seed_memory_id=<canon>, edge_type="supersedes", max_hops=2)` confirms traversal finds the obsoleted ids.

**If `last_run_at: "never"` on EVERY entry, the cron subsystem is dark** — see `references/cron-subsystem-dark-2026-07-06.md` for the diagnostic ladder and the self-preservation behavior the curator should follow when the runner itself isn't running.

## Companion: `scripts/find_stale.py`

Stage 2 needs a SQL filter for "old + low-importance + no valid_until" — Mnemosyne's `inspect` CLI does not expose it. The companion helper lives at `~/.hermes/skills/devops/mnemosyne-curator/scripts/find_stale.py`: a thin SELECT wrapper against `~/.hermes/mnemosyne/data/mnemosyne.db` that prints memory_id, importance, age_days, content_preview (truncated to 80 chars, PII-safe). The helper is **read-only** — it never calls `mnemosyne_invalidate` or `mnemosyne_forget`.

If the helper is not yet present when the cron first fires, the curator falls back to the `mnemosyne_recall` hybrid path described in Stage 2 — slower but functionally equivalent. The curator does not block on the helper.

## Companion: `scripts/emit_supersede_edges.py` (NEW 2026-07-07)

Stage 5 (Linking) takes a list of `(obsolete_id, replacement_id)` pairs and emits one `mnemosyne_graph_link(source, target, relationship='supersedes', weight=0.9)` per pair. The companion helper at `scripts/emit_supersede_edges.py` reads a JSON file of approved pairs (written by the curator after user sign-off on Stage 2) and calls the wrapper tool via the Python API. It is a **write** helper — the curator never runs it without explicit user sign-off, and the output JSON is archived to `~/.hermes/mnemosyne/curator/links-<ISO-date>.json` for audit. Falls back to direct `INSERT INTO graph_edges` if the wrapper is unavailable (Pitfall #16 detection).
