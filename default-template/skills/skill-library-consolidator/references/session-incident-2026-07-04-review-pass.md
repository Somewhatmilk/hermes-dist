# 2026-07-04 — First reviewer + adversary pass on consolidation plan

**Scratchpad:** `da151f3644de4eb0` (HTTP endpoint returned empty body on
retrieval — only the data-journal telemetry row is authoritative)
**Plan summary source:** `~/.hermes/data-journal/telemetry/skill-library-consolidation-2026-07.jsonl`
row 1 (ts 2026-07-04T09:53:33Z)
**Reviewer verdict:** FAIL
**Adversary verdict:** REJECT
**Status at write time:** plan-only, awaiting user-confirm (apply must NOT proceed)

## What the plan claimed

| Field | Plan value | Actual value | Δ |
|---|---|---|---|
| `skill_count` (SKILL.md on disk) | 166 | **167** | +1 |
| `catalog_entries` (.usage.json keys) | 170 | **171** | +1 |
| `unused_on_disk` (view_count==0 AND use_count==0) | 53 | **58** | +5 (the 5 ghosts, so the math is internally consistent) |
| `top-10_total_bytes` | 373,978 | **374,598** | +620 |
| Real catalog ghosts | 5 | **14–15** | +9 to +10 |
| On-disk skills missing from catalog | (not measured) | **11** | new |
| Fold (A) uniqueness | "fits inside obsidian-sd-grid-layout" | obsidian-sd-grid-layout has 0 occurrences of the word "fold" | demote to cross-link |
| Pinned / state=archived | 0 / 0 | 0 / 0 | match ✓ |

## The 5 plan-listed ghosts (verified real)

- `audiocraft-audio-generation` — confirmed missing from disk
- `evaluating-llms-harness` — confirmed missing from disk
- `reddit-fetch-preprocess-v2` — confirmed missing from disk
- `segment-anything-model` — confirmed missing from disk
- `serving-llms-vllm` — confirmed missing from disk

## The 9 additional real ghosts the plan missed

- `camofox-black-screen-fix`
- `devops/goofish-morimens-market`
- `devops/hermes-windows-filesystem-ops`
- `discord-reddit`
- `failures-journal`
- `hermes/session`
- `learn-workflow`
- `meta/cartographer-prompt-gate`
- `meta/hermes-self-improvement`
- `mnemosyne-memory-recall-discipline`
- `reddit-fetch-preprocess`
- `research/web-interaction`
- `session-reflection`

(`mnemosyne-memory-provider` is in `.usage.json` but exists in
`profiles/model-merger/skills/...` not the default profile — partial
ghost, partial cross-profile reference.)

## The 11 on-disk skills missing from the catalog (Action E target)

- `airbnb-listing-optimizer`
- `code-skill-evolve`
- `computer-use`
- `hermes-update-watchdog`
- `karpathy-3-layer`
- `petdex`
- `prompt-evolve`
- `prompt-evolve-loop`
- `prompt-interview-pattern`
- `reddit-research`
- `sillytavern-card-author`

These are real, living skills. `computer-use` and `prompt-evolve-loop`
have heavy per-session load cost because their descriptions trigger
on common task patterns; if the catalog doesn't know about them, the
consolidation survey can't see them, can't archive them, can't refactor
them. **Action E (catalog-gap import) is the new first-class output
of the survey.** Without it, the library grows unmanaged.

## The fold mis-classification (full diff)

`obsidian-callout-foldable-grid/SKILL.md` (8,346 B) is supposed to
fold into `obsidian-sd-grid-layout/SKILL.md` (42,646 B). The
justification is the shared topic of "Obsidian image grids" and the
shared pattern `> [!NOTE|gallery]`.

**What's actually in the smaller skill that's UNIQUE:**

- The native foldable-callout primitive (`[!type]+/-` for default
  open, `[!type]-` for default closed).
- The pitfall: "DO NOT use `<details>` for image grids — callouts
  inside `<details>` are parsed as separate top-level callouts (or
  break parsing entirely)."
- The `display: contents` on `<ul>` trick that makes bullet-list
  card grids actually work.
- The `> [!grid-4 card bg]` Wendystraite bullet-list pattern
  (vs the plain `> [!NOTE|gallery]` efemkay callout pattern).

**What's in the larger skill:** the word "fold" appears 0 times
(verified via `grep -ci fold`). The larger covers 4 grid patterns
(raw HTML, MCL callout, image-gallery masonry, image-layouts
codeblock) and 3 helper plugins. The "foldable" dimension is absent.

**Correct classification:** cross-link, not fold. The two skills
should reference each other in `related_skills:`. The fold
classification overstates the savings (8,346 B entire file vs
roughly half that of truly-unique content) and loses the
foldable-callout knowledge.

## Reproducing the verification

```python
# Save as scripts/survey.py or run inline via terminal
import json, os, re
from pathlib import Path

# Use the Windows-native absolute path, not /c/... (the latter returns
# zero matches from os.walk in MSYS bash — see hermes-windows-filesystem-ops
# Mistake 22 / 26). On Linux: r='/home/<user>/.hermes/skills'.
SKILLS_ROOT = r'C:\Users\somew\.hermes\skills'
USAGE = r'C:\Users\somew\.hermes\skills\.usage.json'

# Exclude internal dirs
EXCLUDE = ('.hub', 'node_modules', '.curator_backups')

# Walk and extract frontmatter 'name:' (NOT folder name — pitfall #10)
on_disk = {}
for root, dirs, files in os.walk(SKILLS_ROOT):
    if any(ex in root for ex in EXCLUDE):
        continue
    for f in files:
        if f == 'SKILL.md':
            content = open(os.path.join(root, f), errors='ignore').read()
            m = re.search(r'^name:\s*([\w\-./]+)', content, re.MULTILINE)
            if m:
                on_disk[m.group(1).strip()] = os.path.join(root, f)

catalog = set(json.load(open(USAGE)).keys())

# Set differences
catalog_only = sorted(catalog - set(on_disk))   # real ghosts
on_disk_only = sorted(set(on_disk) - catalog)   # catalog-gap (Action E)
print(f'catalog={len(catalog)} on_disk={len(on_disk)}')
print(f'real ghosts: {len(catalog_only)}')
print(f'on-disk-only: {len(on_disk_only)}')

# Top-10 sum
sizes = [(p.stat().st_size, n) for n, p in on_disk.items()]
sizes.sort(reverse=True)
print(f'top_10_sum: {sum(s for s, _ in sizes[:10])}')  # must match claim
```

## Cross-skill links from this review

- The `hermes-windows-filesystem-ops` Mistake 22 lesson is the reason
  the `os.walk` path uses the Windows-native form here, not `/c/...`.
  If you use `/c/...` you'll get 0 results and conclude the catalog
  has zero skills — exactly the wrong conclusion. (See also the
  proposed Mistake 26 in hermes-windows-filesystem-ops about CRLF
  regex anchoring.)
- The `verify-before-claim-hardware` skill's "verify by re-running
  the probe" pattern is what the reviewer did here. Every claim in
  the plan was re-verified by independent tool calls; 4 of 5 number
  claims were off.
- The `hermes-misbehavior-diagnosis` pitfall about "fabricated
  success report" applies to the survey numbers in retrospect — the
  survey.py reported 166/170/373978 internally consistent numbers
  that were all slightly wrong, and the per-file match made the
  drift invisible without an independent re-probe.
