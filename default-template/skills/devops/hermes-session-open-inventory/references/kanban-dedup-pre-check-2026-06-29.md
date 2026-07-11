# Kanban dedup pre-check — 2026-06-29 incident

## What happened

A "SOUL.md rework v2" kanban ticket was created on the `default` board
(`t_d766f3b1`) with a 1.9KB body covering 5 universal rules + dispatch
tree + prompt-size gap. The ticket got `archived` 5 minutes later.

## Why it was archived

On `hermes kanban list` after the create, the `default` board already
had:

- `task_v2_souls_add3d41e` — done — prompt-engineering — "Finalize v2 SOUL.md for all 6 profiles (apply user corrections)" — completed 2026-06-27
- `task_v2_souls_corrections_e304cb05` — done — prompt-engineering — "CORRECTIONS: fix v2 SOUL.md (worker missed items + wrong titles)" — completed 2026-06-27
- `task_skill_audit_4cf6e840` — done — default — "Cross-profile skill DRY audit (after v2 SOUL finalized)" — completed 2026-06-27

The deliverable was at
`C:\Users\somew\Documents\hermes-research\ocd-projects\hermes-analysis\research\profile-soul-v2-diff-2026-06-27.md`.
Live state on disk: all 9 `~/.hermes/profiles/<name>/SOUL.md` files
already had the v2 work applied.

The new ticket would have been a **duplicate of completed work**.

## Why the agent missed it

The agent recalled the prior session in `session_search` and saw the
drafts at `C:\Users\somew\Downloads\soul_rework_2026-06-29\` (8 files +
REVIEW.md) from an in-progress rework. The drafts were **inline**
drafts written by `default` in a prior session, NOT the official v2
work. The agent conflated "drafts exist on disk" with "work needs to
be done," and filed a new ticket instead of checking the board first.

## The rule (now in SKILL.md pitfalls)

Before any `hermes kanban create` whose title contains a version
number or "v2/v3/follow-up/refinement/rework":

1. `hermes kanban list --status done,blocked,ready` on the **target
   board** to find prior work in the same task class.
2. If the target board isn't known, `hermes kanban boards list`
   first, then check each.
3. If prior work exists in `done` status: read the deliverable
   artifact, confirm whether the live state already reflects it, and
   only file a new ticket if there's a real delta.
4. If the new ticket is still warranted, mark it `v3+` in the title
   and link the prior ticket in the body (`--parent t_xxx`).

The 4-state inventory trichotomy ("Verified present / Verified
absent / Claim of prior-session work / Unverified") applies here too.
**Mnemosyne recall returns the WORK, not whether the work is still
to be done. Boards are the source of truth for "is this shipped?"**

## The complementary decision: SOUL.md vs Mnemosyne

The "rework v2" instinct was "add the universal floor and dispatch
tree to SOUL.md so every session gets it." The right answer was the
opposite:

- **Live measurement:** `hermes prompt-size` reports 24.3 KB system
  prompt + 86.8 KB tool schemas = ~28K static tokens per turn on
  default / CLI / M3. Industry standard is 8-15K. **Adding to SOUL.md
  makes the gap worse.**
- **The right home for behavioral rules is Mnemosyne**, with
  `importance: 0.7-0.9` and `scope: global` so it fires on
  importance-weighted recall, not every-turn.
- **SOUL.md describes what a profile IS** (Role / Field scope / Voice
  / Routing / 3 short dispatch examples).
- **Mnemosyne holds the behavioral corrections and patterns**
  (anti-duplicate, anti-loop, dispatch tree, prompt-size gap).

Mnemosyne memories created in the 2026-06-29 session:

- `1fd35ad36955c5e4` (importance 0.9) — Default profile dispatch
  decision tree: when to answer inline vs delegate_task vs kanban
  ticket. The "load-bearing" fix for "new session of me doesn't know
  the tools/patterns."
- `20137fe4269b10f3` (importance 0.7) — Hermes prompt-size budget +
  the 13-20K-token gap vs industry standard + the two-stage router
  resolution pattern.
- `a525cc4e5287ec06` (importance 0.7) — v2 SOUL.md rework already
  done + the "SOUL-lean-over-Mnemosyne" policy + live file-size
  table for all 9 profiles.

## Helper script

`~/.hermes/scripts/hermes_kanban_create.py` — written 2026-06-29 to
bypass shell-quoting issues when the body of a `hermes kanban create`
contains colons, dashes, or argparse-confusing text. Pattern:
`hermes_kanban_create.py <board> <title> <body_file> [extra-args...]`.
Reads body from file, invokes `hermes` via `subprocess.run(list,
...)` (no shell). Use this for any ticket body >1KB or containing
colons/dashes/JSON.

## Lessons for next session

1. **Boards are the source of truth for "is this shipped?"** Not
   Mnemosyne, not session_search, not file presence.
2. **Static-prompt overhead is a first-class analysis class.** Run
   `hermes prompt-size` before any "add to SOUL.md" proposal.
3. **The v3 instinct is often wrong.** If the prior v2 was done
   correctly, the new findings belong in Mnemosyne, not in a
   reworked SOUL.md.
4. **Session-bootstrap plugins write to Mnemosyne, never to chat.**
   The `~/.hermes/plugins/session-router/` pattern is the
   canonical "new session of me should know X" solution.
