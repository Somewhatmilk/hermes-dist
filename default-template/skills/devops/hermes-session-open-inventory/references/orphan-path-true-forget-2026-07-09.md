# Orphan-path true-forget + kanban boards-list drift (2026-07-09)

Worked example for Pitfalls **#22** ("Verified-absent paths should be
INVALIDATED, not memorized") and **#23** ("`hermes kanban boards list` is NOT
the source of truth for board inventory"). Both came from a single 2026-07-09
session that surfaced the user-preference signal and the CLI-vs-filesystem
drift, then the user gave the durable "true forget" directive.

## Setup

User asked: "look throught the db for the past changes that i asked be
implemented but we never got around to doing as it as done midway via kanban
task and failed." The "db" turned out to be:

- The kanban DBs at `~/.hermes/kanban/boards/*/kanban.db` (per-board)
- The Mnemosyne DB at `~/.hermes/mnemosyne/data/mnemosyne.db`
- The session transcripts indexed by `session_search`

The agent had multiple `AppData/Local/hermes/...` paths in Mnemosyne from
prior sessions. The user pushed back hard on the orphan-re-confirmation
pattern.

## The 4-session orphan-re-memorization problem

Across sessions 2026-06-24, 2026-07-01, 2026-07-06, and 2026-07-09, prior
agents (and this one) had written Mnemosyne notes with shapes like:

- "RESEARCH STORAGE ... The path `AppData/Local/hermes` is ORPHANED and
  does NOT exist (verified 2026-07-06)."
- "[fact] Hermes dual-dir fact (2026-06-29): TWO script directories exist
  on this Windows machine ... (2) `C:/Users/somew/AppData/Local/hermes/...`"
- "Hermes kanban dispatcher verified working (2026-06-24 v2): The
  hermes-analysis board at `C:\Users\somew\AppData\Local\hermes\kanban\...`"

Each was true at write-time. Each was a "verified absent" fact. None of
them STOPPED existing as a memory; they just kept coming back into recall,
forcing every new session to re-explain "yes, AppData is gone, no, you
shouldn't write there." The user noticed.

## The user's directive (verbatim)

> "yep but i want u to note this is the fourth time in multiple sessio nu
> layed out that AppData/Local/hermes is orphaned meaning u truly never
> deleted it, if u want to forget it just dont even try to memorize it
> after deleting it that its orphaned to truly forget it"

Two parts: (1) **acknowledge the pattern** (this is the 4th time), (2)
**change behavior, not memory** — when removing a path, do not write a
"X is now absent" memory to replace the old "X is here" memory. The
replacement memory has the same effect as the original: it keeps the path
alive in recall.

## What the agent did (and what worked)

Step 1 — Enumerate the orphan-referencing memory IDs:

```
mnemosyne_recall(query="AppData Local hermes kanban boards scripts dual-dir")
# Returned: 8f57..., a108..., c7c5..., 3dba..., e1ae..., 27bd...,
#           fedb..., e5a4..., ef06..., fb45..., bc1e..., 5043...,
#           73d0..., a65b..., e823..., 8e5b..., 5338..., bd90...,
#           8e6b..., aaa1..., 77ac..., 5c24..., 5f84..., 3ae6...,
#           1662..., 481f..., 196c...
```

Step 2 — Classify each (this matters):

| ID | Mentions AppData as... | Disposition |
|---|---|---|
| `8e6b04f4025bdb14` | dual-dir "fact" — claims `AppData/Local/hermes/scripts/` is `$HERMES_HOME/scripts` | **Invalidate** (true-forget) |
| `3ae66ef0ed194039` | "hermes kanban dispatcher verified working" — names the AppData board path | **Invalidate** (true-forget) |
| `5c24ffeb087e59d3` | GEPA install path correction at `AppData/Local/hermes/hermes-agent-self-evolution/` | **Invalidate** (true-forget) |
| `73d0b40171b1f4f5` | "installed tree at `AppData/Local/hermes/hermes-agent/agent/redact.py`" | **Invalidate** (true-forget) |
| `aaa14222d030d3a1` | Scraping-rule — the rule's intent is still valid (don't write hermes-internal), the AppData framing is the only stale bit | **Update** (replace the AppData path with a positive restatement) |
| `e1ae7c9fd1f91531` | Research-storage preference — claims AppData is orphan. The orphan-fact is the issue. | **Update** (replace with positive research-storage rule; no mention of AppData) |
| `e5a40cc27bc27338` | Profile architecture — claims 4 profiles + 5 boards. Numbers stale (live is 1 profile + 2 boards). | **Invalidate** + add a fresh positive memory |
| `a108078129492efb` | "Hermes sub-app fresh install is 5 layers" — mentions `AppData/Local/Programs/hermes-desktop/` for the Electron **install** (NOT kanban) | **Keep** — this is a different concept (Electron installer location, not the agent home) |

Step 3 — Apply true-forget: `mnemosyne_invalidate(id)` for the 5 true-forget
targets. NO replacement memories for the "AppData is orphan" fact.

Step 4 — Update the 2 hybrid cases with positive restatements:

- `aaa14222d030d3a1` → new content keeps the rule's intent ("don't write
  artifacts to hermes-internal dirs; use Downloads/One-Cut-Deeper")
  without mentioning AppData.
- `e1ae7c9fd1f91531` → new content captures the user's actual 2-place +
  future-Obsidian plan, with one explicit note that "future sessions
  should treat AppData paths as non-existent by default and not memorize
  the orphan status."

Step 5 — Add a fresh positive memory for the live 1-profile + 2-board
state (replacing the stale `e5a40cc27bc27338`).

## The kanban boards-list drift (same session)

Same session, different failure: `hermes kanban boards list` returned:

```
SLUG                      NAME                          COUNTS
●   default               Default                       (empty)
```

But the filesystem showed 7 per-board DBs:

```
~/.hermes/kanban/boards/
├── default/             (root kanban.db also lives here as ~/kanban.db)
├── hermes-analysis/
├── joandrew/            ← 21 tasks, 1 blocked, real brand work
├── lab/
├── model-merger.to-merge-2026-06-27/
├── principles/
├── research/
└── sandbox.to-merge-2026-06-27/
```

The agent initially concluded "only `default` exists" based on the CLI
output, then verified via `find` + `ls` that the per-board DBs were real.
Once it queried the on-disk DBs directly with `sqlite3`, the real picture
emerged: joandrew had 21 tasks including a critical blocked one
(`task_ja_homepage_v1_55d3deed`, "joandrew.com.sg homepage sweep").

The full recovery sequence:

```bash
# 1. Enumerate EVERY on-disk board (the source of truth):
for db in /c/Users/somew/.hermes/kanban/boards/*/kanban.db; do
  slug=$(basename $(dirname "$db"))
  tasks=$(sqlite3 "$db" "SELECT COUNT(*) FROM tasks;" 2>&1)
  echo "$slug: $tasks tasks"
done

# 2. Cross-check against CLI (which lags):
hermes kanban boards list

# 3. If a board's DB exists but the CLI doesn't see it, read the
#    per-board DB directly with sqlite. Use Windows backslash paths
#    (the forward-slash /c/Users/... form is flaky on sqlite3 CLI):
sqlite3 -header -column "C:\\Users\\somew\\.hermes\\kanban\\boards\\joandrew\\kanban.db" \
  "SELECT id, status, assignee, title FROM tasks WHERE status NOT IN ('done','archived') ORDER BY created_at;"
```

The joandrew board's blocked task was the only piece of in-progress work
in the entire system. The CLI would have said "nothing blocked
anywhere." Direct sqlite read revealed the real state.

## The board-archive-batch narration pattern

Once the cleanup was approved, the agent moved 6 stale boards to
`~/hermes-archive-2026-07-09/` (the user pre-cleared this archive-dir
pattern; it's the same one the 2026-07-06 home audit used and the one
`hermes-soft-delete-discipline` documents for bulk cleanup). The
narration pattern that worked (per `hermes-soft-delete-discipline`):

```bash
# Per-board narration, one line at a time (not a batched report):
echo "Moving hermes-analysis → $ARCHIVE/..."
mv "$SRC/hermes-analysis" "$ARCHIVE/" && echo "  ok"

echo "Moving lab → $ARCHIVE/..."
mv "$SRC/lab" "$ARCHIVE/" && echo "  ok"

# ... 4 more, same shape ...
```

Each step is a single visible move + an `ok` confirmation. The user can
interject at any point. This is the "narration per step, not a batched
report" rule from `hermes-soft-delete-discipline` applied to kanban
board cleanup specifically.

## What the agent also caught mid-cleanup

While moving the boards, the agent found 2 zero-byte stub files at
`boards/hermes-analysis.db` and `boards/joandrew.db` (not the
directories — files at the same level). These were leftover from failed
board creates. The agent used normal `rm` for them per the
`hermes-soft-delete-discipline` "What soft-delete is for vs not for"
table ("Truly transient state" / "0-byte placeholders from a failed
create" → normal `rm` is fine).

## Probe sequence summary (the durable lesson)

For any "look at the kanban" / "what's blocked" / "show me my boards"
request:

```bash
# 1. CLI (fast but possibly stale):
hermes kanban boards list

# 2. Filesystem (canonical — always do this):
for f in ~/.hermes/kanban/boards/*/board.json; do
  slug=$(basename $(dirname "$f"))
  echo "$slug: $(jq -r '.name + \" | \" + (.description // \"\")' < "$f")"
done

# 3. Per-board task state (Windows backslash paths are reliable):
for db in ~/.hermes/kanban/boards/*/kanban.db; do
  slug=$(basename $(dirname "$db"))
  echo "=== $slug ==="
  sqlite3 "C:\\Users\\somew\\.hermes\\kanban\\boards\\$slug\\kanban.db" \
    "SELECT status, COUNT(*) FROM tasks GROUP BY status;"
done

# 4. The filesystem is the source of truth. The CLI registry is best-effort.
```

For any "clean up an orphan path" request:

```bash
# 1. Verify absent (multi-path + CLI, see Pitfall #15):
ls /c/Users/somew/AppData/Local/hermes 2>&1 | head -3
ls /c/Users/somew/.hermes/hermes-agent 2>&1 | head -3

# 2. Find every Mnemosyne note that still encodes the orphan:
mnemosyne_recall(query="<orphan keywords>", limit=20)

# 3. For each hit that encodes the absence, mnemosyne_invalidate(<id>) — NO replacement.

# 4. Update hybrid cases with positive restatements (keep rule intent, drop the orphan).

# 5. Verify nothing in SOUL.md / config / skills still references the path:
grep -r "<orphan path>" ~/.hermes/{SOUL.md,config.yaml,skills/,hooks/,profiles/*/SOUL.md}
```

## Why this matters

The user-preference signal here is real and durable: a positive-fact
memory for an absent path is a **memory leak**. Every session that
memorizes "X is absent" is one more session that has to NOT re-confirm
it, but the recall surface keeps surfacing it. True forget = `invalidate`
+ nothing. The orphan should be invisible, not a recurring confirmation
the agent has to re-process.

Pair this with the canonical-pitfall from `kanban-orchestrator` v4.1.0:
"On-disk kanban DBs > CLI `boards list` when they disagree." Two skills,
one rule: the filesystem is the source of truth; the CLI is best-effort
and can lag.
