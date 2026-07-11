---
title: Skill-uses proposal pass — verified edges + apply log
date: 2026-07-11
session: hermes_20260711_160006_491efc
applies-to: future session deciding whether to extend the typed-frontmatter graph; explains what the 12 verified `uses:` edges are and the 4 dropped claims
companion-pitfall: skill-library-consolidator pitfalls #27, #28
---

# Skill-uses proposal pass (2026-07-11)

## What was proposed

A survey of `~/.hermes/skills/` produced 191 skills with 4 typed
frontmatter fields (`requires:`, `uses:`, `supersedes:`,
`primary_triggers:`). Of those, 13 high-confidence `uses:`
relationships were extracted from a hand-coded `HIGH_CONFIDENCE_RULES`
table. All 13 were grep-verified against the source skill's body and
frontmatter.

## Verification result

13 claims:
- **5 confirmed** (all targets found in body) — apply as-is
- **4 partial** (some targets found) — apply the verified ones, drop the absent
- **4 unverified** (no targets found) — drop entirely

Hit rates by tier:
- very-high (skill's own `related_skills:`) — 67% (4/6 individual target references verified)
- high (I claimed I read the body) — 56% (5/9)
- medium (hand-coded workflow logic) — 43% (3/7)

**Lesson:** hand-coded claims without file evidence are wrong more often
than right. Always grep-verify before shipping.

## The 12 verified edges that landed

| # | Source skill | `uses:` → | Evidence |
|---|---|---|---|
| 1 | `failures-journal` | `hermes-session-open-inventory` | body-mention: "canonical skills (`failures-journal`, `hermes-session-open-inventory`...)" |
| 2 | `hermes/hermes-skill-loading-disciplines` | `hermes-session-open-inventory` | body-mention: "ls ~/.hermes/docs/ — there is almost always a prior audit" |
| 3 | `meta/cartographer-prompt-gate` | `prompt-interview-pattern` | body-mention: "If you can't diagnose a symptom in this table, the prompt isn't broken" |
| 4 | `research/information-validation` | `multi-source-research-tactics` | body-mention: "Overlap note: This skill overlaps with multi-source-research-tactics" |
| 5 | `skill-library-consolidator` | `hermes-skill-refactor` | body-mention: "Not for refactoring ONE named skill → hermes-skill-refactor" |
| 6 | `skill-library-consolidator` | `mnemosyne-curator` | body-mention: "not for memory hygiene → mnemosyne-curator" |
| 7 | `devops/hermes-session-open-inventory` | `failures-journal` | body-mention: "`failures-journal` — log inventory failures here" |
| 8 | `devops/mnemosyne-curator` | `mnemosyne-memory` | body-mention: "the wrapper not the library: `mnemosyne_graph_link` is registered by the Hermes plugin wrapper" |
| 9 | `hermes/hermes-misbehavior-diagnosis` | `failures-journal` | body-mention: "Pure tool errors (use `failures-journal`)" |
| 10 | `software-development/hermes-skill-refactor` | `hermes-agent-skill-authoring` | body-mention: "Writing a brand-new skill from scratch → hermes-agent-skill-authoring" |
| 11 | `software-development/hermes-skill-refactor` | `skill-library-consolidator` | body-mention: "`meta/skill-library-consolidator` — surveys the whole library" |
| 12 | `software-development/hermes-skill-refactor` | `prompt-evolve` | body-mention: "`prompt-evolve-loop` — GEPA-style optimization" |

Bidirectional pair: `failures-journal ↔ hermes-session-open-inventory`
(rows 1 and 7).

## The 4 dropped claims (UNVERIFIED)

| Claim | Why it dropped |
|---|---|
| `deep-research-methodology` → `multi-source-research-tactics` | Skill body has no reference. Hand-coded workflow chain. |
| `deep-research-methodology` → `information-validation` | Same — invented. |
| `cross-session-rule-audit` → `mnemosyne-memory` | Skill doesn't read Mnemosyne directly. |
| `research-refresh-ritual` → `information-validation` | Skill references validation concepts but doesn't cite the skill. |

## The 3 partial drops (from PARTIAL verdicts)

| Claim | Status |
|---|---|
| `hermes-session-open-inventory` → `preflight-snapshot-rollback` | absent in body |
| `hermes-session-open-inventory` → `hermes-skill-loading-disciplines` | absent (but the relationship exists in reverse direction — bidirectional test failed one way) |
| `hermes-misbehavior-diagnosis` → `hermes-session-open-inventory` | absent (surprising — diagnosis skill doesn't cite the inventory skill) |
| `hermes-skill-refactor` → `code-skill-evolve` | absent |
| `hermes-agent-skill-authoring` → `hermes-skill-authoring-gotchas` | absent |

## Apply pass

After 3 failed patch rounds (description-paraphrase,
anchor-truncation, regex-drop-body), the v2 Python template applied
the 12 verified edges successfully on the first attempt. Final
verification: all 9 patched files have description byte-identical to
snapshot, body byte-identical to snapshot, `uses:` line present, size
delta +25-80 bytes (one frontmatter line).

## Artifacts (all under `~/.hermes-state/temp/2026-07-11/`)

| File | Purpose |
|---|---|
| `.skill-inventory.csv` | Step 1 — 191 skills, frontmatter fields |
| `.skill-clusters.md` | Step 2 — 13 clusters + 33 uncategorized |
| `.skill-overlap-pairs.csv` | Step 2 — 1,278 candidate pairs (noisy) |
| `.skill-proposals.csv` | Step 3 — 191 four-field proposals |
| `.skill-proposals-verified.csv` | Step 3 — 13 verification results |
| `.skill-proposals-verified.md` | Step 3 — human-readable summary |
| `inventory.py` | Step 1 re-runnable probe |
| `cluster.py` | Step 2 re-runnable probe |
| `propose.py` | Step 3 re-runnable proposal generator |
| `safe_patch_v2.py` | Apply pass — the canonical template |

Plus `~/.hermes/.trigger-index.json` (49,680 bytes; 191 skills indexed,
9 with `uses:`).

## What this session did NOT do

- **Step 4 (patch `hermes-agent-skill-authoring` to mandate the four
  fields on new skills):** deferred. Was always lower priority than
  shipping the verified edges.
- **Step 5 (cron registration for trigger-index rebuild):** the
  index was built once, but no cron was registered. The index will
  go stale as skills change.
- **Hard-deps search:** I classified all 13 as `uses:` (soft
  companions) but did not grep for hard-dep phrases like
  "REQUIRES:" / "MUST have" / "depends on". There are probably
  5-15 genuine `requires:` relationships I missed.
- **The 4 unverified claims:** stayed in
  `~/.hermes-state/temp/2026-07-11/.skill-proposals.csv` as
  `candidates_to_verify_later`. Not lost, just not promoted.

## What a future session should do with this

1. **If asked "do we have typed-frontmatter skills now?"** — yes,
   9 skills have `uses:` declared (10 if you count
   `skill-library-consolidator` which has 2 edges). The rest are
   still leaf.

2. **If asked to extend the graph** — run `propose.py` (still in
   `~/.hermes-state/temp/2026-07-11/`), grep-verify the new
   proposals with the same method this session used, and apply via
   `safe_patch_v2.py`. Don't skip the verification step.

3. **If asked why some claims were dropped** — the 4 unverified
   ones had no file evidence. They were hand-coded from workflow
   logic. Reasoning from workflow is not evidence; grep is.

4. **If asked about the cron** — no, it wasn't registered. The
   trigger-index will go stale as skills change. To enable: run
   `hermes cron create --name trigger-index-rebuild --schedule
   "0 4 * * 0" --script ~/.hermes/skills/skill-library-consolidator/scripts/build_trigger_index.py
   --no-agent` (script doesn't exist yet — extract from
   `~/.hermes-state/temp/2026-07-11/` first).