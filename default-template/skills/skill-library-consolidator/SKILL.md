---
name: skill-library-consolidator
uses: [hermes-skill-refactor, mnemosyne-curator]
description: "Class-level workflow for surveying the Hermes skill library, detecting contradictions between adjacent skills, and producing a plan to archive, fold, or refactor. Use when the user says 'consolidate', 'audit the skills', 'look at bloat', 'clean up the library', 'review the entire skills dir', or when 30+ days have passed since the last survey. Not for refactoring a single named skill (use hermes-skill-refactor) and not for memory hygiene (use mnemosyne-curator). Embodies the 2026-07-11 evidence + deliverable discipline (pitfalls #24-#30): every claim is a live probe, every proposal carries a confidence flag, every patch verifies byte-identity, the deliverable is a changed library, not a markdown doc."
version: 1.5.0
author: Hermes Agent (default profile)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, consolidation, audit, library, lifecycle, meta, bloat, evidence, deliverable, patch-safety]
    category: meta
    related_skills: [hermes-skill-refactor, hermes-self-improvement, hermes-skill-authoring-gotchas, hermes-agent-skill-authoring, mnemosyne-curator, cross-session-rule-audit, data-journal, addon-protocol]
    config: []

---
# Skill Library Consolidator

A survey-then-plan workflow for keeping the Hermes skill library from
growing without limit. Runs the seven steps in order, writes the plan
to scratchpad, and pauses for human review before any apply.

## When to use

- The user says "consolidate", "audit the skills", "look at bloat",
  "clean up the library", "trim the catalog", "any dead skills?"
- `find ~/.hermes/skills -name SKILL.md | wc -l` returns 100+
  and the last survey was >30 days ago (per auto-log in
  `data-journal/telemetry/skill-library-consolidation-*.jsonl`).
- A new skill is created in a category that already has 3+ skills
  (likely duplication).
- `.usage.json` shows `view_count==0` AND `use_count==0` for >60 days
  (orphan signal — but note the catalog bulk-import on 2026-06-21
  means the first 60d window is meaningless).

## When NOT to use

- User wants to refactor ONE named skill → `hermes-skill-refactor`
- User wants to clean up memory → `mnemosyne-curator`
- User wants to write a new skill → `hermes-agent-skill-authoring`
- A skill is failing >10% — that's evolution, not consolidation
  → `code-skill-evolve` or `prompt-evolve`

## The seven steps

### 1. Survey

Count and characterize the library. Don't act on findings yet.

```bash
# Top-level structure (exclude .hub internals)
find ~/.hermes/skills -name SKILL.md -not -path '*/.hub/*' \
  -not -path '*/node_modules/*' | wc -l

# Top-10 largest (highest-leverage refactor wins)
find ~/.hermes/skills -name SKILL.md -printf '%s %p\n' \
  | sort -rn | head -10

# Per-category distribution
```

Or run the re-runnable survey:
`python3 ~/.hermes/skills/meta/skill-library-consolidator/scripts/survey.py`
(writes summary to stdout, full per-skill row to
`data-journal/telemetry/skill-library-consolidation-YYYY-MM.jsonl`).
For recovering a plan when the scratchpad HTTP endpoint returns
empty (pitfall #15), use
`scripts/recover_scratchpad.py <id>` — it reads the full plan
directly from `~/.hermes/mnemosyne/data/mnemosyne.db`. See `references/session-incident-2026-07-04-review-pass.md` for
the first-pass review that surfaced pitfalls 11–17 (catalog gap,
fold mis-classification, arithmetic drift, scratchpad retrieval,
Mnemosyne touchpoint). See
`references/2026-07-04-3way-reviewer-experiment.md` for the
controlled comparison that surfaced pitfall #20 (output
contract must be in the dispatch context, not just the
profile name).

**Completion criterion:** a concrete table of (bytes, path) for the
top-10 largest, plus a category-distribution count. No "look at the
big ones" — name each file. **Verified counts (2026-07-04 lesson):**
the four canonical counts (`SKILL.md on disk` from a recursive walk,
`catalog entries` from `.usage.json` keys, `top-10 byte sum` from
`awk '{s+=$1}END{print s}'` over the per-file listing, and
`category-distribution count` from the walk bucketed by parent dir)
must agree. If any disagree by more than zero — off-by-one is the
canonical bug — the survey is wrong and the auto-log must NOT be
written until the discrepancy is resolved. The set difference is
the diagnosis (`on_disk − catalog` = on-disk-only skills, the gap
the survey ignores; `catalog − on_disk` = real ghosts, the survey's
ghost list before subtracting false positives). Use the
`scripts/survey.py` re-runnable probe which already does these diffs
and exits non-zero if the counts don't reconcile.

### 2. Detect contradictions

Scan all descriptions for shared noun phrases. Two skills are a
*real* contradiction if:

- They cover the same domain (e.g., both Obsidian image grids)
- Their triggers are close (e.g., both fire on "use when rendering X")
- One skill's content would fit inside the other **without losing
    information** — see pitfall #11 below for the "partial overlap
    is not a fold" rule, and the size-vs-uniqueness test in the
    procedure

**False-positive patterns** (look like contradictions, aren't):

- Platform tags (`windows`, `linux`, `docker` appearing in 10+ skills
  — that's a platform hint, not domain overlap)
- Product name (`hermes`, `mnemosyne` — these are the toolchain)
- Sibling tools (`claude-code / codex / opencode` — they're siblings
  by design, not duplicates)
- Different lifecycle stages (`electron-app-reverse-engineering` vs
  `electron-desktop-patterns` vs `electron-python-integration` —
  three stages of one workflow, not a contradiction)

**Completion criterion:** a list of contradiction pairs/groups,
each tagged REAL or FALSE-POSITIVE with one-line rationale.

### 3. Draft plan (write to scratchpad, no apply yet)

Classify every finding into one of four actions:

| Action | When | Example |
|---|---|---|
| **A. Archive** | Skill is unused AND the host can't use it (e.g., Mac skills on a Windows host) | `apple/*` on a Windows host |
| **B. Catalog-ghost cleanup** | Entry in `.usage.json` but no `SKILL.md` on disk (verified by frontmatter `name:` field, NOT folder name — see pitfall #10) | 1 entry on 2026-07-04: `reddit-fetch-preprocess-v2` (4 others reported in earlier surveys were renamed-skill false positives) |
| **C. Fold contradiction** | Two skills cover the same ground; fold smaller into larger | `obsidian-callout-foldable-grid` → `obsidian-sd-grid-layout` |
| **D. Refactor top-N largest** | Skill > 20KB and below peer norm | Top-10 of `find … -printf '%s %p' \| sort -rn` |
| **E. Catalog-gap import** | `SKILL.md` exists on disk but its `name:` frontmatter is NOT in `.usage.json` (set diff `on_disk − catalog`) | 2026-07-04 catch: `airbnb-listing-optimizer, code-skill-evolve, computer-use, hermes-update-watchdog, karpathy-3-layer, petdex, prompt-evolve, prompt-evolve-loop, prompt-interview-pattern, reddit-research, sillytavern-card-author` — 11 living skills the catalog had never seen. Run `hermes curator import <name>` per entry to register them in `.usage.json` so future surveys see them. Without Action E, the catalog-count off-by-one never closes, and refactor/archive decisions based on `view_count==0` miss real working skills. |

**Hard rule:** do NOT apply any of A/B/C/D in this step. The skill
is plan-only. Apply requires explicit user-confirm in a follow-up
turn.

**Completion criterion:** a plan with concrete file paths and
expected byte-savings, written to scratchpad.

### 4. Reviewer (skipped on first run, required on apply)

`delegate_task(profile="reviewer", goal="audit plan", context="<plan + sibling SKILL.md excerpts>")`

Reviewer returns a verdict. FAIL → fix the plan, re-dispatch.

**Skip condition:** first run of this skill in a session, OR user
explicitly says "skip the formal review." Human-in-the-loop is the
default reviewer until the procedure has been run 3+ times and the
user trusts the detection.

### 5. Adversary (skipped on first run, required on apply)

`delegate_task(profile="adversary", goal="rebut plan", context="<plan + reviewer verdict>")`

Adversary returns rebuttal. REJECT → fix, re-dispatch.

**Skip condition:** same as step 4.

### 6. Apply (user-confirm required, per-target via `hermes-skill-refactor`)

For each action in the plan, run the appropriate per-target
procedure. **Do not run them in parallel** — each refactor is
context-heavy and the model needs the previous result.

- **A (archive):** `hermes curator archive <name>` OR move the skill
  dir to `~/.hermes/skills/.hub/quarantine/`
- **B (ghost cleanup):** `hermes curator remove <name>` to drop the
  `.usage.json` entry
- **C (fold):** read both skills, write the larger with folded
  content, delete the smaller, update `related_skills:` in both
  directions
- **D (refactor):** follow `hermes-skill-refactor` Recipe B for each
  target

**Patch-safety pre-check (NEW 2026-07-11, pitfalls #28-#30):** before
any `write_file` / `patch` to a SKILL.md, run the
`scripts/safe_patch_v2.py` template (canonical at
`~/.hermes-state/temp/2026-07-11/safe_patch_v2.py`). It enforces:
snapshot-first at `~/.hermes-state/snapshots/<topic>__<date>/`,
frontmatter parse + insert-only-no-replace, body byte-identity
pre-write + post-write. Never patch SKILL.md frontmatter with a
truncated `old_string` anchor — the `patch` tool will fuzzy-match
and truncate the description field.

**Mnemosyne touchpoint:** after apply, run `mnemosyne_invalidate`
on any memory entry that referenced a folded or archived skill by
name. Search first: `mnemosyne_recall(query="<old-skill-name>")`.

**Completion criterion:** a before/after table with bytes saved,
contradictions resolved, ghosts cleared.

### 7. Verify (reviewer on post-merge state)

`delegate_task(profile="reviewer", goal="verify apply", context="<before/after table + applied diffs>")`

PASS → ship. FAIL → revert (use `.curator_backups/` snapshots).

## Triggers (config-driven, not hardcoded)

| Signal | Default threshold | Override via |
|---|---|---|
| Skill count growth | >10 new in 30 days | `~/.hermes/config.yaml` `consolidation.thresholds.count_growth_30d` |
| Last used | >60 days | `consolidation.thresholds.last_used_days` |
| Contradiction detected | any | n/a (always fires) |
| User request | any | n/a (always fires) |

Hardcoding thresholds into this skill body is a self-imposed
constraint. Move them to config when the skill graduates from
plan-only to wired-cron.

## Auto-log (per user preference 2026-07-02)

Every survey writes one row to:
`~/.hermes/data-journal/telemetry/skill-library-consolidation-YYYY-MM.jsonl`

Fields: `ts`, `skill_count`, `catalog_entries`, `orphans`, `pinned`,
`unused_on_disk`, `stale_60d`, `contradictions` (list with
`id`/`kind`/`name`/`target`), `archive_candidates`, `status`
(`survey-only` / `applied` / `reverted`), `scratchpad_id`.

Do NOT ask "should I save?" — append and move on (per
`meta/hermes-self-improvement` auto-log rule).

## Pitfalls

1. **Naive "unused = view_count==0."** This filter is wrong because
   a skill can be heavily used via cron-job `attached_skills` or
   per-profile SOUL.md `load_skill` references without ever
   showing up in `.usage.json`. Cross-check before archiving. (The
   `survey.py` script flags this gap; close it manually with
   `grep -r "skill-library-consolidator" ~/.hermes/profiles/ ~/.hermes/cron/`
   before declaring a skill unused.)

2. **Confusing consolidation with evolution.** If a skill is
   *failing* (broken, drift, user complaints), that's
   `code-skill-evolve` or `prompt-evolve`, not this skill.
   Consolidation is about library *shape* (count, overlap,
   staleness), not per-skill quality.

3. **Auto-applying the plan.** This skill is plan-only by design.
   The 4-step plan (A/B/C/D) is a *proposal* for human review,
   not a commit. Apply requires explicit user-confirm.

4. **Surveying in-repo skills (`~/.hermes/hermes-agent/skills/`)
   and user-local skills (`~/.hermes/skills/`) as one set.** They
   are separate trees with separate change controls. The
   user-local tree is the primary survey target; the in-repo tree
   ships with hermes-agent upstream and changes via git.

5. **Folding without reading.** "These two are both about Obsidian
   grids, fold them" without reading both is a recipe for losing
   the smaller skill's specific pitfall section. Read both,
   end-to-end, before any fold.

6. **Ignoring the `.usage.json` `created_at` field.** The
   `2026-06-21T12:08:18` mass-import date means the "stale" filter
   is meaningless for 60+ days from that date. The 2026-07-04
   first survey showed 0 skills with `last_viewed_at > 60d`
   because every skill in the catalog was created < 30 days
   before. Don't conclude "nothing's stale, we're good" — the
   window hasn't elapsed yet.

7. **Triggering on noun-phrase clusters without checking
   false-positive patterns.** A cluster of 10 skills all
   mentioning `windows` is not a contradiction. Always classify
   each cluster as REAL or FALSE-POSITIVE with rationale before
   drafting the plan.

8. **Skipping the auto-log.** The 2026-07-02 user preference is
   hard: every audit produces a row. Forgetting the log means
   the next session can't see what was surveyed, what was found,
   and what was deferred.

9. **Treating the `meta/` folder as a skill itself.** `meta/` is
   a housing folder for cross-cutting skills
   (`hermes-self-improvement`, `cartographer-prompt-gate`,
   `cross-session-rule-audit`, `hermes-memory-architecture`).
   Routing rules should be path-agnostic, not special-case
   `meta/`. Invoking "view meta" produces an ambiguous path —
   the agent should ask which meta/ skill, not auto-load all four.

10. **Catalog-ghost detection by folder name, not frontmatter
    `name:`** (FOUND 2026-07-04 in this skill's own first run). The
    `.usage.json` catalog key matches the frontmatter `name:` field,
    NOT the folder name. Many skills live in folders like
    `mlops/models/audiocraft/SKILL.md` but declare
    `name: audiocraft-audio-generation` in their frontmatter. The
    initial `survey.py` used `p.parent.name` for ghost detection
    and produced 4 of 5 false positives
    (`audiocraft-audio-generation`, `evaluating-llms-harness`,
    `segment-anything-model`, `serving-llms-vllm` — all present on
    disk; only `reddit-fetch-preprocess-v2` was a real ghost).
    If a user had trusted that ghost list, they would have deleted
    4 legitimate skills. **Fix:** extract the frontmatter `name:`
    field via regex and compare against catalog keys. The patched
    `survey.py` (v1.0.1+) uses `get_frontmatter_name(p)` for ghost
    detection. `_check_ghosts.py` had this right from the start —
    consolidate, don't fork.

11. **"Fold" requires full content subsumption, not partial
    overlap** (FOUND 2026-07-04). The "fits inside without losing
    information" test for Action C is not satisfied by
    shared-topic overlap. Example: `obsidian-callout-foldable-grid`
    (8 KB) shares the `> [!NOTE|gallery]` pattern with
    `obsidian-sd-grid-layout` (42 KB), but its unique content
    (the foldable-callout primitive `[!type]+/-`, the `<details>`
    pitfall, the `display: contents` on `<ul>` trick) does NOT
    appear in the larger. The `grep -ci fold obsidian-sd-grid-layout/SKILL.md`
    returns 0 — the larger doesn't even mention the word. The
    correct classification was "cross-link" (mention each other
    in `related_skills:`), NOT "fold." **Rule:** before any C
    classification, grep the target for the *unique* content of
    the source skill, not the topic they share. If unique-content
    terms are absent, demote to cross-link.

12. **Listing the unused-cross-check as pitfall #1 doesn't
    enforce it** (FOUND 2026-07-04). Pitfall #1 says cross-check
    `view_count==0` against `~/.hermes/profiles/` and
    `~/.hermes/cron/` before archiving. The 2026-07-04 plan
    archived 5 apple/* skills without running that cross-check —
    the gap between "pitfall listed" and "pitfall applied" was
    not surfaced anywhere in the workflow. **Fix:** add a
    hard-gate step to the Apply (step 6) procedure that requires
    a positive cross-check result before any archive action.
    The exact form: `grep -rE "<skill-name>" ~/.hermes/profiles/ ~/.hermes/cron/`
    must return 0 hits OR the cross-check must be explicitly
    documented as not-required (with reason). Otherwise the
    apply pass aborts. Encode this as a checklist item, not a
    paragraph in a pitfalls list.

13. **Treating `.usage.json` as ground truth hides the
    catalog-gap** (FOUND 2026-07-04, found 11 skills). 11 on-disk
    skills (`airbnb-listing-optimizer`, `code-skill-evolve`,
    `computer-use`, `hermes-update-watchdog`, `karpathy-3-layer`,
    `petdex`, `prompt-evolve`, `prompt-evolve-loop`,
    `prompt-interview-pattern`, `reddit-research`,
    `sillytavern-card-author`) had `SKILL.md` files but no entry
    in `.usage.json`. The original survey treated `.usage.json`
    as authoritative for "skill count" and never looked at the
    inverse set diff. The library is BIGGER than the catalog
    knows. **Fix:** Action E (catalog-gap import) is now a
    first-class survey output. The set difference `on_disk −
    catalog` is reported in every auto-log row as a new field,
    `on_disk_only`. Without this, the library grows
    unmanaged — these 11 skills consumed disk space, runtime
    prompt tokens (for the always-loaded ones), and SOUL.md
    references with zero visibility in the consolidation plan.

14. **Top-10 byte sum needs arithmetic verification, not per-file
    match** (FOUND 2026-07-04, 620-byte drift). The 2026-07-04
    survey claimed `top_10_total = 373,978`; the actual sum was
    `374,598`. Per-file sizes matched exactly, but the sum was
    off by 620 bytes (likely a hand-arithmetic error when
    copying the number into the telemetry row). The auto-log
    field looked plausible; no test caught it. **Fix:** the
    `survey.py` script must compute the sum with `awk '{s+=$1}
    END{print s}'` over the actual file listing, not by hand.
    The summary field is auto-derived from the per-skill table,
    so the two cannot diverge.

15. **Scratchpad HTTP retrieval can return empty for a real id**
    (FOUND 2026-07-04). The consolidation plan was written to
    scratchpad id `da151f3644de4eb0`, but the HTTP endpoint
    `http://localhost:8765/v1/scratchpads/<id>` returned an
    empty body to the reviewer subagent. The only authoritative
    copy of the plan summary was the
    `data-journal/telemetry/skill-library-consolidation-2026-07.jsonl`
    row — which is a summary, not the full plan. Future review
    passes that try to fetch the scratchpad will see nothing.
    **Fix:** the auto-log row must contain a full enough plan
    summary to reconstruct the plan without the scratchpad
    (concrete paths, byte savings, contradictions with their
    classification). Add a `plan_full` field that mirrors the
    scratchpad content. Future review passes can fall back to
    the telemetry row if the scratchpad endpoint returns empty.
    **Tier-2 fallback (FOUND 2026-07-04 in this skill's own
    audit pass):** the telemetry row is a *summary*, not the
    full plan. If the scratchpad endpoint returns empty AND the
    telemetry row lacks `plan_full`, the full plan is still
    recoverable from the Mnemosyne SQLite database at
    `~/.hermes/mnemosyne/data/mnemosyne.db`:
    ```bash
    sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db \
      "SELECT content FROM scratchpad WHERE id='<id>'"
    ```
    The `scratchpad` table mirrors what the HTTP endpoint
    exposes; reading it directly bypasses the empty-body
    failure. Always try this BEFORE concluding the plan is
    unrecoverable. Do NOT rely on the Mnemosyne MCP tools
    (`mnemosyne_recall`, etc.) for this — they search
    episodic/working memory, not the `scratchpad` table. The
    `scripts/recover_scratchpad.py` probe wraps this query and
    handles the missing-db / missing-id error paths; run it
    instead of hand-typing the SQL each time.

16. **Mnemosyne touchpoint is required for ANY skill name that
    appears in memory**, not just for the action being applied
    (FOUND 2026-07-04). `obsidian-callout-foldable-grid` was
    created 2026-07-04, 4 days before the 2026-07-04 review
    pass. A freshly-created skill can already have Mnemosyne
    recall entries referencing it (the next session may have
    generated them via the auto-recall on skill load). The
    step-6 Mnemosyne touchpoint (`mnemosyne_recall` then
    `mnemosyne_invalidate`) must be run for every skill name
    touched by the apply pass, including names that survived
    unchanged (the larger skill in a fold pair, for example).
    The naive "only invalidate references to the *removed* skill"
    misses entries that named the *kept* skill in the context
    of the fold.

17. **Re-running survey.py against the live tree resets `pinned`
    and `state=archived` counters to zero on each run** (FOUND
    2026-07-04 by counter cross-check). If the catalog shows
    `pinned=0` and `state=archived=0`, those are *catalog*
    attributes, not disk attributes — and the survey needs to
    report both views. The current auto-log fields `pinned`
    and `archived` come from `.usage.json`, not from the on-disk
    skill dirs. A skill that's `state=archived` in the catalog
    but has its dir still on disk is in a limbo state — the
    `archive_candidates` row in the plan needs to skip names
    that are already `state=archived`.

18. **Re-deriving the workflow from scratch when this skill
    already exists** (FOUND 2026-07-04 by the agent that drafted
    the v1.0.0 plan without first loading this skill). The
    parent-skill trap: the consolidation workflow feels
    obvious — survey, detect contradictions, plan — so a new
    session will write it inline rather than `skill_view(name=
    'skill-library-consolidator')`. The skill is at v1.1+ for
    a reason; it encodes 17 pitfalls the inline derivation
    will repeat. **Fix:** at the start of any consolidation
    task, run `skill_view(name='skill-library-consolidator')`
    and read the entire Pitfalls section BEFORE drafting the
    plan. The seven-step procedure + pitfalls encode every
    known failure mode — the inline derivation is the failure
    mode. This is a hard pre-condition for steps 1–3, not a
    "consider loading" suggestion.

19. **Surveying only `~/.hermes/skills/` ignores the
    per-profile bundles** (FOUND 2026-07-04 by the
    `apple/*` cross-check failure). Default profile lives at
    `~/.hermes/skills/`. Every other profile (adversary,
    reviewer, communicate-design, model-merger,
    software-engineering) has its own bundle at
    `~/.hermes/profiles/<name>/skills/`, seeded by
    `hermes_cli/profiles.py::seed_profile_skills()` at
    profile-create time. Each bundle is a 70–96-file copy of
    most of the global skills, with 8–35 differences per
    profile. The `.bundled_manifest` in each profile is a
    content-hash snapshot of 72 entries. **Implications for
    the apply pass:** any action that touches a skill by name
    (A archive, B ghost cleanup, C fold, D refactor) MUST
    walk all 6 trees (1 global + 5 per-profile), not just
    the global. The 2026-07-04 plan's "archive apple/*" would
    have removed 5 files from `~/.hermes/skills/` while
    leaving 25 copies in 5 per-profile bundles untouched —
    misleading the user about disk/prompt-token savings. **Fix:**
    every Action A/B/C/D row in the plan gets a `bundles_to_update`
    field listing which `.bundled_manifest` files reference the
    target by frontmatter `name:` or folder name. Apply pass
    updates each bundle's `.bundled_manifest` and (for A and
    C) removes/updates the per-profile skill directory. For
    bundle-aware archive, set `NO_BUNDLED_SKILLS_MARKER` per
    profile to opt out of bundled-skill seeding — that's
    cheaper than 5-way surgical removal when the user wants
    the skill gone everywhere.

20. **The "reviewer" and "adversary" subagent dispatches don't
    load the actual profile personalities** (FOUND 2026-07-04
    by the 3-way reviewer experiment). `delegate_task`
    subagents are leaf workers with fresh context. The
    `profile=` parameter routes through the per-profile
    `config.yaml` and prepends the `agent.system_prompt` to
    the subagent's instructions — but the `personalities.`
    blocks (adversary/retrospect for the adversary profile;
    reviewer/devils_advocate for the reviewer profile) are
    NOT automatically activated. The 2026-07-04 3-way
    experiment produced useful output because the dispatch
    context block explicitly told each subagent which output
    contract to follow (PROPOSAL/OBJECTION/VERDICT for
    adversary; PASS/FAIL/INSUFFICIENT_EVIDENCE for
    reviewer). Without that explicit contract, the subagent
    would have produced a generic review in default-voice.
    **Fix:** when dispatching to a specialist profile for
    the first time in a session, the dispatch context must
    contain the output contract from the profile's
    `personalities.<name>.system_prompt` block, NOT just
    reference the profile name. The 2026-07-04 contract
    blocks are recorded in `references/2026-07-04-3way-reviewer-experiment.md`
    for reuse. To test the *actual* profile behavior (e.g.
    to A/B test the personality tone), spawn the profile
    as a real subprocess with `hermes -p <name>` and message
    it directly — that's the only way the `personalities.`
    block actually fires.

21. **The cross-profile write guard blocks `write_file` and
    `patch` on `~/.hermes/config.yaml`** (FOUND 2026-07-04).
    Agents get: *"Refusing to write to Hermes config file.
    Agent cannot modify security-sensitive configuration.
    Edit ~/.hermes/config.yaml directly or use 'hermes
    config' instead."* The guard exists for good reason (a
    bad config edit can lock you out of Hermes entirely),
    but the workflow consequence is: **never draft a config
    change as `patch`/`write_file` and expect it to land —
    route through the supported CLI instead.** Two routes
    work:
      - `hermes config set <dotted.key> <value>` — works
        for existing keys; can also create new keys under
        a parent that already exists (e.g.
        `sessions.live_validated_days` was created by
        `hermes config set` even though it didn't exist
        before). Use this for value changes.
      - `hermes config edit` — opens `$EDITOR` with the
        live config. Use this for adding new top-level keys
        or restructuring blocks.
    The opposite mistake (don't write to `~/.hermes/.env`
    or any `~/.hermes/profiles/*/config.yaml` from a leaf
    agent; use the per-profile `hermes config set` with the
    active `-p` flag) compounds the same problem. **This
    pitfall is not in the original 7-step procedure because
    the procedure's apply pass is plan-only by design (step
    6 requires user-confirm). When the apply pass actually
    runs and the action is a config change, the user (or
    the agent in a controlled context) must run `hermes
    config set` themselves — `write_file` will not land.**

22. **Field-name ambiguity in the same block** (FOUND
    2026-07-04 in `sessions:`). When two fields describe
    the same intent with different units (e.g.
    `recent_session_days: 3` AND
    `recent_session_count: 10`), the sweep script / cron
    must pick a preference explicitly. Don't leave it
    silent. Document the choice in the block's own comment
    so future maintainers don't second-guess. Concrete
    pattern: comment above the field pair:
    `recent_session_count: 10  # sweep script prefers this over recent_session_days`
    Without the comment, the next refactor will think one
    of them is dead code and delete it.

23. **Internal metrics are not the goal (FOUND 2026-07-08,
    user explicit).** When surveying for "token reduction,"
    "prompt cache hit rate," "file count," or any other
    internal metric, the metric is a *proxy* for the real
    goal — preserve the source material, no lost information.
    Optimizing for the proxy at the expense of the goal
    (delete to shrink the count, even if some of the
    deletions are source-bearing; rewrite to save tokens,
    even if the rewrite loses nuance) is the consolidation
    failure mode. The user named this 2026-07-08 when the
    audit produced a 25-skill drift map (Pattern B) and a
    7-archive plan (Pattern D) and explicitly corrected:
    *"correctness and no lost information is the goal;
    token reduction is a side-effect."* **Rule:** every
    action in the plan must include a "what is preserved"
    justification, not just a "what is removed" or "what
    is shrunk" justification. If a delete loses source
    material that the user might want later, the delete
    is wrong even if it saves tokens. Concrete decision
    tree when planning a delete:
    (1) is the content represented elsewhere durable
    (Mnemosyne, Obsidian, a project deliverable, the
    user-cited canonical source)? → safe to delete from
    this surface.
    (2) is the content NOT yet captured anywhere durable?
    → extract to Mnemosyne / Obsidian / `Documents/hermes-research/`
    BEFORE deleting, then delete.
    (3) is the content ephemeral / speculative / test
    data? → delete without capture.
    The "extract before delete" rule makes (3) the only
    case where the delete is uncompensated. Full canon:
    `~/.hermes/skills/devops/filesystem-audit-and-consolidate/references/audit-user-guardrails-2026-07-08.md`.
    Related: pattern "misleading-predecessor-canon" in
    `hermes-skill-loading-disciplines` (skills that look
    deprecated but are actually referenced).

24. **Heuristic-evidence — every consolidation claim must be backed by a live probe (NEW 2026-07-11).** Eyeballing cluster sizes ("10 audit skills", "15 research skills") and writing them into a proposal doc is the failure mode. The raw count (`find ~/.hermes/skills -name SKILL.md | wc -l`) is one probe; it must be cross-checked against an independent traversal (`ls ~/.hermes/skills/*/SKILL.md ~/.hermes/skills/*/*/SKILL.md | wc -l`), and per-category breakdown must be a separate probe. Write the evidence to `~/.hermes-state/temp/<date>/.skill-inventory.csv` — the CSV IS the audit trail. Without it, the auto-log row carries unfounded numbers into future sessions. Companion: `references/consolidation-patterns-2026-07-11.md` Pattern 24.

25. **Confidence flags on every typed-frontmatter proposal (NEW 2026-07-11).** When the survey produces `requires:` / `uses:` / `supersedes:` / `primary_triggers:` proposals per skill, every cell carries a confidence flag: `high` (body explicitly says / frontmatter already declares), `medium` (cluster co-membership + newer-skill heuristic), `low` (inferred from description similarity only), `n/a` (intentionally empty). Empty `[]` is a signal of "considered, none found" — write `[]` explicitly, never omit the field. The user reviews low-confidence rows in one pass; high-confidence rows can be applied with a summary. Companion: Pattern 25.

26. **Proposal doc ≠ deliverable (NEW 2026-07-11, user-pushed correction).** The single biggest trap on 2026-07-11: the agent produced a 19 KB markdown architecture doc as the "deliverable" and never touched the library. The user had to ask "what's your plan?" on the next turn to surface the gap. **Rule:** the deliverable of a consolidation pass is a *changed library* (or a CSV awaiting user-confirm), not a markdown doc. **Check before declaring a session done:**
    1. Did I touch any `~/.hermes/skills/<name>/SKILL.md`? YES → apply pass ran. NO → did I produce a CSV with proposed changes? YES → apply pass deferred for user review, OK. NO → I produced a doc and called it work. **Wrong.**
    2. Did the user have to ask "what's your plan?" after my last turn? YES → I produced planning artifacts instead of executing. NO → verify the library state changed.

    **Tier-2 fallback:** when the library is too big for safe single-session surgery (e.g. 190 skills, 190-row CSV), the right deliverable IS the CSV + an apply-confirm prompt. The user reviews; the apply pass runs in the next session with their annotations. NOT a 19 KB proposal doc. Companion: Pattern 26.

27. **Hand-coded `uses:` claims need grep-evidence before shipping (NEW 2026-07-11).** When proposing dependencies between skills, reasoning from workflow logic ("A → B makes sense") is NOT evidence. On 2026-07-11, 13 hand-coded `uses:` claims were grep-verified against source skill bodies. Result: 4 failed (deep-research-methodology → multi-source-research-tactics, deep-research-methodology → information-validation, cross-session-rule-audit → mnemosyne-memory, research-refresh-ritual → information-validation, hermes-agent-skill-authoring → hermes-skill-authoring-gotchas). Hit rates by tier: medium (hand-coded) 43%, high (in-body evidence I claimed to have read) 56%, very-high (skill's own `related_skills:`) 67%. **Rule:** every `requires:` / `uses:` / `supersedes:` proposal must carry file-evidence (grep hit, body-mention, or frontmatter-declaration), not workflow reasoning. Hand-coded proposals go to `candidates_to_verify_later`, never to apply. Companion: `references/skill-uses-proposals-2026-07-11.md`.

28. **Multi-section text patch verification must check every section (NEW 2026-07-11).** When patching a SKILL.md (or any multi-section document), the verification ladder is: (1) snapshot exists, (2) description byte-identity vs snapshot, (3) body byte-identity vs snapshot (everything after `---` closer), (4) `uses:` line present in frontmatter, (5) size delta within expected range (+25-80 bytes for one frontmatter line). Checking only the section you intended to change misses everything else. On 2026-07-11 the patch tool's `patch` calls were checked only for `uses:` presence; descriptions got paraphrased and bodies got truncated without detection. Three rounds of failure followed before body byte-identity verification caught the truncation bug. Companion: Pattern 27.

29. **Patch tool old_string match is fuzzy and dangerous on multi-line YAML (NEW 2026-07-11).** The `patch` tool's fuzzy match will replace text at the first match of the old_string, which can be a partial match. If your anchor string is shorter than the description field, the patch may replace just the anchor with your new content, truncating the rest. **Fix:** either include the FULL old text (no truncation) OR use a Python script that parses frontmatter, inserts a new line, and verifies byte-identity of all sections. Never rely on the patch tool for frontmatter edits without full-content anchors. Companion: Pattern 28.

30. **Regex drop-body bug — `re.match` with non-greedy capture drops content after the match (NEW 2026-07-11).** When using `re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.DOTALL)` to split frontmatter, `tail = m.group(3)` is just the closer `\n---`, NOT the rest of the file. The body (everything after the closer) is in `text[m.end():]`, NOT in `tail`. Conflating these discards the body silently. On 2026-07-11 this turned a 66 KB skill into a 4-line stub in one round-trip; recovered via snapshot. **Fix:** explicitly construct `new_text = head + new_fm + closer + body` where `body = text[m.end():]`. Verify body byte-identity pre- and post-write. The canonical safe-patch template lives at `~/.hermes-state/temp/2026-07-11/safe_patch_v2.py`. Companion: Pattern 29.

## Related skills

- `hermes-skill-refactor` — per-skill procedure; this skill
  identifies *which* skills to refactor, refactor does the work
- `meta/hermes-self-improvement` — umbrella; this skill is the
  step-5 (consolidate) reference for skill library bloat
- `mnemosyne-curator` — sister workflow for memory, not skills
- `cross-session-rule-audit` — runs a different audit
  (rule compliance) but uses the same auto-log pattern
- `hermes-skill-authoring-gotchas` — fixes broken CLI refs in
  individual skills; complementary
- `hermes-agent-skill-authoring` — write a new skill; the
  companion to refactor and to this consolidator
- `devops/filesystem-audit-and-consolidate` — the
  filesystem-level (not skill-level) audit workflow; holds the
  user canon "9 audit guardrails, 2026-07-08" which this
  skill's pitfall #23 summarizes. Load that skill when the
  audit scope extends beyond `~/.hermes/skills/`.

## Verification

- [ ] Survey wrote a row to `data-journal/telemetry/skill-library-consolidation-YYYY-MM.jsonl`
- [ ] Plan written to scratchpad with concrete file paths
- [ ] No apply step ran without explicit user-confirm
- [ ] Each contradiction tagged REAL or FALSE-POSITIVE with rationale
- [ ] Unused-skill filter cross-checked against cron-referenced and SOUL-loaded skills (pitfall #12)
- [ ] On-disk skill count == catalog entry count (or `on_disk_only` set is non-empty and listed as Action E)
- [ ] Top-10 byte sum matches `awk` over the per-file listing (pitfall #14)
- [ ] Fold candidates passed unique-content grep against target skill (pitfall #11)
- [ ] Mnemosyne `recall` + `invalidate` runs for every touched skill name (pitfall #16)
- [ ] If scratchpad HTTP retrieval returned empty during review, the Tier-2 SQLite fallback was attempted before declaring the plan unrecoverable (pitfall #15)
- [ ] Plan was drafted AFTER `skill_view(name='skill-library-consolidator')` returned the current version — never re-derived inline (pitfall #18)
- [ ] Every Action A/B/C/D row has a `bundles_to_update` field listing per-profile `.bundled_manifest` files that reference the target (pitfall #19)
- [ ] Reviewer / adversary dispatches include the output contract from `personalities.<name>.system_prompt` in the context block — profile name alone is not enough (pitfall #20)
- [ ] Every Action in the plan includes a "what is preserved" justification, not just a "what is removed" one (pitfall #23, user explicit 2026-07-08). Internal metrics (token cost, file count, prompt-cache hit rate) are not the goal — correctness and no-lost-information are the goal; metrics are a side-effect.
- [ ] Every consolidation claim (cluster size, overlap pair, count) is backed by a live probe in this session, not by prior-session assertion (pitfall #24).
- [ ] Every typed-frontmatter proposal carries a confidence flag (`high` / `medium` / `low` / `n/a`); empty arrays are explicit (pitfall #25).
- [ ] The session's deliverable is a changed library OR a CSV awaiting user-confirm — NOT a markdown proposal doc (pitfall #26). If the user asked "what's your plan?" after the agent's last turn, the deliverable is wrong.
- [ ] Every `requires:` / `uses:` / `supersedes:` proposal in the plan was verified by grep against the source skill's body or frontmatter (pitfall #27). Hand-coded proposals go to `candidates_to_verify_later`, never to apply.
- [ ] Before any `write_file` / `patch` to a SKILL.md frontmatter, snapshot existed at `~/.hermes-state/snapshots/<topic>__<date>/` AND verification checked (a) description byte-identity, (b) body byte-identity, (c) `uses:` line present, (d) size delta within range (pitfall #28).
- [ ] Patches to multi-line YAML frontmatter used either full-content anchors OR the `safe_patch_v2.py` template (pitfall #29). Never a truncated `old_string`.
- [ ] Any Python regex used to split frontmatter was tested with body byte-identity pre-write AND post-write (pitfall #30). The body is `text[m.end():]`, NOT `m.group(3)`.

## Changelog

- **v1.5.0 (2026-07-11):** Added pitfalls #27-#30 from the
  skill-uses proposal pass and patch disaster. Pitfall #27 =
  hand-coded `uses:` claims need grep-evidence (43% hit rate on
  medium-tier, 4/13 claims failed verification). Pitfall #28 =
  multi-section text patch verification ladder (description +
  body + uses + size delta; checking only one section is
  insufficient). Pitfall #29 = patch tool's fuzzy-match
  truncates to anchor; use full-content anchors or
  `safe_patch_v2.py`. Pitfall #30 = regex drop-body bug when
  `re.match` with non-greedy capture conflates `m.group(3)`
  with body. Also bumped the description to reference pitfalls
  24-30 (was 24-26) and added a "patch-safety pre-check" callout
  in Step 6 with pointer to `safe_patch_v2.py`. Frontmatter tag
  grew `patch-safety`. Verification checklist grew 4 hard-gate
  items mirroring pitfalls 27-30. Triggered by the 2026-07-11
  apply pass where 3 of 4 patch rounds on the same 5 files
  failed different ways; snapshot reverted cleanly each time
  but the verification ladder had to be rebuilt from scratch.

- **v1.4.0 (2026-07-11):** Absorbed Patterns 24, 25, 26 from `references/consolidation-patterns-2026-07-11.md` into the canonical Pitfalls section. Pitfall #24 = heuristic-evidence (every claim is a live probe, not a prior-session assertion). Pitfall #25 = confidence flags on every typed-frontmatter proposal (`high` / `medium` / `low` / `n/a`, empty arrays are explicit). Pitfall #26 = proposal doc ≠ deliverable (the deliverable is a changed library or a CSV awaiting user-confirm; a 19 KB markdown doc that "explains the plan" is the failure mode). Description updated to include "review the entire skills dir" trigger and to embed the evidence + deliverable discipline. Verification checklist grew 3 hard-gate items mirroring pitfalls 24-26. Frontmatter tags grew `evidence` and `deliverable`. Triggered by user-pushed correction in session `hermes_20260711_160006_491efc` after the agent produced a 19 KB architecture proposal doc instead of touching the library.
- **v1.3.0 (2026-07-08):** Added pitfall #23 ("internal metrics
  are not the goal") from the 2026-07-08 audit pass. The user
  explicitly corrected the framing of "token reduction" as
  the goal — the goal is "correctness and no lost information,"
  and metrics are a side-effect. The "extract before delete"
  decision tree is now part of pitfall #23. Verification
  checklist grew one hard-gate item. Companion reference:
  `~/.hermes/skills/devops/filesystem-audit-and-consolidate/references/audit-user-guardrails-2026-07-08.md`.
- **v1.2.0 (2026-07-04):** Added pitfalls 18–20 from the 3-way
  reviewer experiment and per-profile bundle discovery.
- **v1.1.0 (2026-07-04):** Added pitfalls 11–17 from the first
  reviewer + adversary pass on the 2026-07-04 consolidation plan
  (scratchpad `da151f3644de4eb0`).
- **v1.0.1 (2026-07-04):** Patched `survey.py` to extract
  frontmatter `name:` field instead of folder name.
- **v1.0.0 (2026-07-04):** First version. 7-step workflow with
  pitfalls 1–9.