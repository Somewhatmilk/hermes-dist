---
name: addon-protocol
description: "Threat-tiered sandbox + evidence-loop workflow for any new addon (skill, config edit, cron registration, script, patch). Use when user says 'try something new', 'add X', 'set up Y', 'register Z', or any prompt that touches production paths. Loads BEFORE any addon action to classify threat level and pick the right verification surface. Distinct from hermes-self-improvement (which governs evolution/reflexion) and from skill-library-consolidator (which governs library shape). Load this for the *act* of adding; load skill-library-consolidator for *surveying what exists*."
version: 1.0.0
author: Hermes Agent (default profile)
license: MIT
metadata:
  hermes:
    tags: [addon, protocol, threat-tier, sandbox, evidence-loop, workflow, safety]
    category: meta
    related_skills: [hermes-self-improvement, skill-library-consolidator, hermes-skill-authoring, hermes-session-open-inventory, failures-journal, data-journal]
---

# Addon Protocol — Threat-Tiered Sandbox + Evidence Loop

The discipline governing HOW Hermes adds, edits, or registers anything
in the user's install. Two failure modes motivate this protocol:

1. **Over-careful:** every change sandboxed, every change slow. Burns
   user time and produces no observable difference from direct execution.
2. **Under-careful:** direct edits to `~/.hermes/skills/`,
   `~/.hermes/config.yaml`, or live cron without verification. Ships
   broken changes and trusts agent self-report.

The protocol picks one of three paths based on **threat level**, then
requires **evidence on completion**, not confidence.

## When to use

- User says "try something new", "add X", "set up Y", "register Z",
  "build a skill that does W", "edit the config", "register a cron".
- Any prompt that ends with a question mark about future state of the
  install: "can you make X work", "should we add Y", "what if we did Z".
- Any tool call sequence that ends in `write_file` or `patch` against
  a production path.

## When NOT to use

- One-off task execution (read a file, run a search, answer a question)
  — no addon, no protocol needed.
- Pure skill authorship when the user explicitly requested a skill
  with no risk implication — still invoke, but expect LOW threat.
- Memory writes (`mnemosyne_remember`, etc.) — those have their own
  contract; not addon work.

## The threat-tier table

| Threat | Examples | Sandbox? | Where | Validation |
|---|---|---|---|---|
| **LOW** | Reads, searches, drafts, new files in `~/.hermes-state/temp/<date>/` or `~/.hermes/docs/`, SKILL.md in `~/.hermes/sandboxes/<topic>/` | No (direct) | Production path or sandbox depending on user intent | Smoke test: parses, description-match hits |
| **MEDIUM** | Edit existing `SKILL.md`, add scripts to `~/.hermes/scripts/`, modify `~/.hermes/config.yaml`, register a cron | **Yes** | `~/.hermes/sandboxes/<topic>/` first, then `patch` to production | Functional test + diff review |
| **HIGH** | Touch `hermes-agent/` source, modify the loader, schema changes to Mnemosyne, anything affecting session-bootstrap | **Yes + snapshot + dry-run** | `~/.hermes/sandboxes/<topic>/` + `~/.hermes-state/snapshots/<topic>__<date>/` | Multi-step: import, run, regression, evidence |

**Escape hatch:** if LOW-threat validation takes ≤2 minutes, sandbox anyway.
The threshold isn't "what's the risk?" — it's "what's the cost of being
wrong vs. cost of sandboxing?" When in doubt, sandbox.

## The evidence loop (not confidence, evidence)

For every step, "done" means producing *verifiable artifacts*, not
conclusions. The checklist:

| Claim type | Evidence required |
|---|---|
| "Skill X loads correctly" | `skill_view X` returns content; `skills_list \| grep X` matches |
| "Description doesn't collide" | `grep` results showing no other skill has the same primary trigger |
| "Frontmatter validates" | Re-read SKILL.md, confirm YAML parses, fields present |
| "Trigger index is fresh" | `jq '.indexed_at'` returns timestamp within tolerance; file size > 0 |
| "Skill actually auto-loads" | Real prompt test, see the skill in context window |
| "Cron fires" | Per Pitfall #10 (skill-library-consolidator): `Last run: ok` + `test -f <script>` + last stdout/artifact exists |

**Anti-false-confidence checklist** (run BEFORE declaring done):

- ☐ Did I run the actual probe, or did I infer from the description?
- ☐ If I inferred, is the inference labeled? (e.g., "likely works because X")
- ☐ Would the user be able to reproduce my verification step?
- ☐ Is the artifact path I claim actually the one I checked?
- ☐ Did I check for the silent-no-op case (Pitfall #10)?

## The seven-step ADDON procedure

When invoking this protocol, run these in order. Each step has a
completion criterion; skipping any is a protocol violation.

### 1. Classify threat level

Apply the table above. If uncertain, classify UP (higher threat, more
sandbox), not down. Write the classification in your response so the
user can override before you proceed.

**Completion criterion:** one-line threat-level statement visible to user.

### 2. Pick the sandbox path

| Threat | Path |
|---|---|
| LOW | Direct. Use `~/.hermes-state/temp/<date>/` for working files, `~/.hermes/docs/` for read-only docs. |
| MEDIUM | `~/.hermes/sandboxes/<topic>/` for working copy. Snapshot to `~/.hermes-state/snapshots/<topic>__<date>/` before any edit. |
| HIGH | `~/.hermes/sandboxes/<topic>/` + `~/.hermes-state/snapshots/<topic>__<date>/` + dry-run if possible |

**Completion criterion:** the chosen paths exist on disk (or are documented as `not needed` for LOW).

### 3. Iterate the change

For the actual edit, allow as many iterations as needed inside the
sandbox. Do NOT move to step 4 until the sandbox version works.

**Completion criterion:** the sandbox version passes its own functional test.

### 4. Generate evidence

Run the anti-false-confidence checklist. Produce at minimum:
- File path of the artifact
- Command that verified it
- Output (or excerpt) showing the verification succeeded

**Completion criterion:** evidence block visible in your response.

### 5. Promote

Use `patch` or `write_file` to move from sandbox to production. For
MEDIUM/HIGH, include the user-confirm checkpoint BEFORE promotion.

**Completion criterion:** production path matches the sandbox path's content (or diff is documented).

### 6. Verify post-promotion

Re-run the evidence probe against the production path. The post-promotion
probe is what catches the "it worked in sandbox but broke in production"
case.

**Completion criterion:** post-promotion probe output visible.

### 7. Log to failures-journal if anything was non-trivial

Per Reflexion (Pattern 1 of hermes-self-improvement): any tool error,
test fail, or user correction gets one line appended. Skip only if the
change was trivial and the user did not correct.

**Completion criterion:** either a JOURNAL.md line, OR explicit "trivial, no log" note.

## Pitfalls (numbered to align with skill-library-consolidator)

- `references/2026-07-11-staging-dir-session-start.md` — working artifacts go to `~/Downloads/<topic-slug>_<YYYY-MM-DD>/` via the `staging_dir()` helper, NOT `~/.hermes-state/temp/`. Call `staging_dir()` as the FIRST tool call of any session.
- `references/2026-07-11-surgical-frontmatter-insertion.md` — adding a single frontmatter field requires Python with body byte-identity verification at 4 checkpoints, NOT the `patch` tool. 4-round failure sequence (description-replaced, description-truncated, body-discarded, 4th round succeeded).

### 1. "Try something new" is too vague to act on alone

The user prompt "try something new" or "add X" doesn't carry threat
level implicitly. **Always classify explicitly** before acting. If
the user says "just do it," that's a LOW-threat signal with explicit
user override — still classify, but note the override.

### 2. Sandbox as virtue signal, not discipline

Sandboxing a change without iterating inside the sandbox is theater.
The point of the sandbox is *iteration without production risk*, not
"we wrote it twice." Skip the sandbox only when iteration is genuinely
not needed (one-shot config value, single-line script).

### 3. Confidence ≠ evidence

"I checked it and it works" is confidence. Evidence is "I ran
`jq '.indexed_at' ~/.hermes/.trigger-index.json` and got
`2026-07-11T16:30:00`." The agent's self-report is the failure mode
this protocol exists to defeat.

### 4. Skipping post-promotion verification

A common shortcut: the sandbox version works, promote it, declare
done. The promotion step can break things (path change, permissions,
missing parent dir). Always re-run the probe against the production
path.

### 5. The "validation is fast" escape hatch backfires

The escape hatch "if validation is ≤2 min, sandbox anyway" means
**always sandbox** for unknown cost. The 2-minute number is a
*floor*, not a ceiling. When in doubt, sandbox.

### 6. Logging "trivial, no log" for everything

The trivial-no-log exception is for true one-line edits. A new skill,
a new cron, a new script, a config block — none of these are trivial
even if they take 5 minutes. When the work *creates* an artifact
(SKILL.md, script.py, jobs.json entry), log it.

### 7. Forgetting the snapshot for HIGH-threat edits

`~/.hermes-state/snapshots/` is the rollback target. A HIGH-threat
edit without a snapshot is a recovery scenario waiting to happen.
The snapshot can be a single file `cp`; the cost is 2 seconds, the
benefit is undo-able mistakes.

### 8. Promoting before the user sees the evidence

For MEDIUM/HIGH threat, the user-confirm checkpoint is between step
4 (evidence) and step 5 (promote). If you promote without checkpoint,
the protocol is violated. The user gets to see the evidence + the
sandbox diff before anything touches production.

## When the user overrides the threat classification

If the user says "skip the sandbox, just edit it directly" or "this
is fine, do it":

1. Acknowledge the override explicitly.
2. Note the original threat level you'd have classified.
3. Apply the lower-threat path.
4. **Still run evidence step 4** — the override changes the path,
   not the verification standard.

The override applies to *where* you work, not to *how rigorously*
you verify.

## Related skills

- `hermes-skill-authoring` — for the four-field frontmatter convention
  (requires/uses/supersedes/primary_triggers) that this protocol's
  addon creation step invokes
- `skill-library-consolidator` — for surveying what exists; this
  protocol governs the act of adding, not the shape of the library
- `hermes-session-open-inventory` — for verifying install state
  *before* any addon touches it
- `failures-journal` — Pattern 1 of self-improvement; the log target
  for step 7
- `hermes-self-improvement` — meta-umbrella; this protocol is one
  sub-protocol within the self-improvement space
- `data-journal` — auto-log for any addon that produced data worth
  comparing across runs (timings, classifications, decisions)
- `skill-library-consolidator/references/consolidation-patterns-2026-07-11.md`
  Patterns 24-26 — heuristic-evidence, confidence flags, proposal-doc-≠-deliverable.
  Companion patterns for addon work that touches the library.

## Verification

- [ ] Threat level classified explicitly in response before any action
- [ ] Sandbox path chosen matches the threat tier
- [ ] Sandbox version iterated to functional pass
- [ ] Anti-false-confidence checklist filled out (5 items)
- [ ] Evidence block visible in response (artifact + command + output)
- [ ] User-confirm checkpoint shown for MEDIUM/HIGH before promotion
- [ ] Post-promotion probe re-run against production path
- [ ] Failures-journal line appended OR explicit "trivial, no log"
- [ ] Snapshot exists at `~/.hermes-state/snapshots/<topic>__<date>/` for HIGH

## Changelog

- **v1.0.0 (2026-07-11):** Initial version. Captured from session
  `hermes_20260711_160006_491efc` where the user corrected the
  "sandbox everything" over-careful framing with the threat-tier
  + escape-hatch version. Companion to the consolidation patterns
  24-26 in `skill-library-consolidator/references/consolidation-patterns-2026-07-11.md`.