# Consolidation Patterns — 2026-07-11 Session

Companion to `SKILL.md`. Captures lessons from the 2026-07-11 modularity
discussion that should govern future consolidation passes. Numbered to align
with `SKILL.md` pitfall numbering — the SKILL.md body can absorb these as
official pitfalls (#24, #25, #26) when next edited.

## Pattern 24 — Heuristic-evidence

Every consolidation claim must be backed by a live probe, not by memory or
prior-session assertion. The minimum evidence shape:

```bash
# Raw count (one probe)
find ~/.hermes/skills -name SKILL.md -not -path '*/.hub/*' \
  -not -path '*/node_modules/*' | wc -l

# Cross-checked count (different traversal)
ls ~/.hermes/skills/*/SKILL.md ~/.hermes/skills/*/*/SKILL.md 2>/dev/null | wc -l

# Per-category distribution
for cat in $(ls ~/.hermes/skills/); do
  count=$(find ~/.hermes/skills/$cat -name SKILL.md -maxdepth 3 2>/dev/null | wc -l)
  printf '%-30s %4d\n' "$cat" "$count"
done

# Evidence file — write this
python3 -c "
import os, re, glob
rows = []
for path in glob.glob(os.path.expanduser('~/.hermes/skills/*/SKILL.md')) + \
         glob.glob(os.path.expanduser('~/.hermes/skills/*/*/SKILL.md')):
    try:
        content = open(path).read()
        fm = re.match(r'---\n(.*?)\n---', content, re.DOTALL)
        meta = {}
        if fm:
            for line in fm.group(1).splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    meta[k.strip()] = v.strip()
        rel = len([s for s in meta.get('related_skills', '').split(',') if s.strip()])
        rows.append({
            'path': path,
            'name': meta.get('name', os.path.basename(os.path.dirname(path))),
            'bytes': os.path.getsize(path),
            'category': path.split(os.sep)[-3],
            'description_first_line': meta.get('description', '')[:120],
            'related_skills_count': rel,
        })
    except Exception as e:
        rows.append({'path': path, 'error': str(e)})
import csv, sys
w = csv.DictWriter(sys.stdout, fieldnames=['path','name','bytes','category','description_first_line','related_skills_count'])
w.writeheader()
for r in rows: w.writerow(r)
" > ~/.hermes-state/temp/2026-07-11/.skill-inventory.csv
```

The 2026-07-11 failure: claimed "190 skills" / "10 audit-cluster skills" /
"15 research-cluster skills" with no probes. The raw count is real
(~190), but the cluster sizes were eyeballed. A 2-minute CSV pass
produces the audit trail.

## Pattern 25 — Confidence flags on every proposal

When the survey produces a list of proposed changes (`requires:` /
`uses:` / `supersedes:` / `primary_triggers:` per skill), every cell gets
a confidence flag. The user reviews low-confidence rows in one pass;
high-confidence rows can be applied with a summary.

CSV shape:

```csv
path,name,requires,requires_confidence,uses,uses_confidence,supersedes,supersedes_confidence,primary_triggers,notes
~/.hermes/skills/X,Y,[foo],"high",[bar],"medium",[],"n/a",["verify X"],"X is newer than foo, body references it"
~/.hermes/skills/Z,Q,[],[],[],"n/a",[old-q],"low",["validate Z"],"guess: old-q was renamed to Q"
```

Flag definitions:

- **high**: agent is certain (body explicitly says, frontmatter already
  declares the relationship in some form)
- **medium**: likely (cluster co-membership + newer-skill heuristic)
- **low**: guess (inferred from description similarity only)
- **n/a**: field intentionally empty (`supersedes:` on a leaf skill)

Empty `[]` is a signal of "considered, none found" — do not omit the
field, write `[]` explicitly. See `hermes-agent-skill-authoring` Step 0.4.

## Pattern 26 — Proposal doc ≠ deliverable

The single biggest trap on 2026-07-11: the agent produced a 19 KB markdown
doc as the "deliverable" and never touched the library. The user had to
ask "what's your plan?" on the next turn to surface the gap.

**Rule:** the deliverable of a consolidation pass is a *changed library*
(or a CSV awaiting user-confirm), not a markdown doc.

**Check before declaring a session done:**

1. Did I touch any `~/.hermes/skills/<name>/SKILL.md`?
   - YES → apply pass ran, OK
   - NO → did I produce a CSV with proposed changes?
     - YES → apply pass deferred for user review, OK
     - NO → I produced a doc and called it work. **Wrong.**

2. Did the user have to ask "what's your plan?" after my last turn?
   - YES → I produced planning artifacts instead of executing.
   - NO → possibly OK, but verify the library state changed.

**Tier-2 fallback:** when the library is too big for safe single-session
surgery (e.g. 190 skills, 190-row CSV), the right deliverable IS the CSV
+ an apply-confirm prompt. The user reviews; the apply pass runs in the
next session with their annotations. NOT a 19 KB proposal doc.

## Connection to existing SKILL.md pitfalls

These three patterns extend but do not contradict the existing pitfall
set. Specifically:

- **Pattern 24** operationalizes the "Verified counts" rule in Step 1's
  Completion criterion (currently embedded in prose).
- **Pattern 25** is a new methodology that doesn't exist anywhere in the
  current SKILL.md — fills a gap for the typed-frontmatter proposal
  workflow.
- **Pattern 26** parallels Pitfall #3 (Auto-applying the plan) and
  Pitfall #18 (Re-deriving the workflow from scratch) — they cover
  plan-only mode and inline-derivation mode, but Pattern 26 covers the
  third mode (writing a doc instead of doing the work).

## Pattern 27 — Cross-link to addon-protocol

Consolidation patterns 24-26 govern the *shape* of the library (count,
overlap, staleness). The **act** of adding a new skill — including the
threat-tier classification, sandbox discipline, and evidence loop — is
governed by the new umbrella `meta/addon-protocol` (created
2026-07-11, session `hermes_20260711_160006_491efc`).

**Cross-reference map:**

| Task | Skill to load |
|---|---|
| "Should I add a new skill?" | `meta/addon-protocol` (classify threat, sandbox, iterate, evidence) |
| "What skills already exist?" | `skill-library-consolidator` (survey step 1) |
| "Are any of them duplicates of the new one?" | `skill-library-consolidator` (detect contradictions step 2) |
| "I added a skill, did it load?" | `meta/addon-protocol` step 6 (post-promotion verification) |
| "The library is bloated, clean up" | `skill-library-consolidator` (full 7-step procedure) |

**Anti-pattern:** when the user says "add a new skill that does X,"
the right move is `meta/addon-protocol` first (decide threat, decide
sandbox path, decide iteration depth), THEN `hermes-agent-skill-authoring`
(skill-specific frontmatter convention), THEN `skill-library-consolidator`
Step 2 (does the new skill duplicate an existing one?). Loading the
skills in any other order produces either a skill that doesn't fit
the threat tier or a skill that duplicates an existing one.

## What to do with this reference file

When the SKILL.md is next edited (any reason), absorb these three
patterns as Pitfalls #24, #25, #26 in the canonical numbering. Until
then, the SKILL.md cross-link in this file's existence is implicit —
the reference is read alongside the SKILL.md when a consolidation pass
loads both via `skill_view(name='skill-library-consolidator')`.

## Provenance

Captured 2026-07-11 in session `hermes_20260711_160006_491efc`. The
proposal doc that prompted this reference is at
`~/.hermes/docs/hermes-modularity-architecture-proposal-2026-07-11.md`
(not consulted as ground truth — Pattern 26 specifically warns against
this — but cited as the artifact whose existence surfaced the pattern).