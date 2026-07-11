---
title: Safe frontmatter insert (v2)
date: 2026-07-11
session: hermes_20260711_160006_491efc
applies-to: any SKILL.md frontmatter edit where you need to add a line (e.g. `uses: [foo]`) without disturbing description or body
companion-pitfall: skill-library-consolidator pitfalls #28, #29, #30
---

# Safe frontmatter insert — the v2 template

## Why this exists

On 2026-07-11, the agent tried three different approaches to insert a
`uses: [...]` line into 9 SKILL.md files. Each approach failed in a
different way:

| Round | Tool | Bug | Damage |
|---|---|---|---|
| 1 | `patch` | old_string matched and replaced the description field | 5 descriptions paraphrased/shortened |
| 2 | `patch` | old_string was a partial anchor; tool truncated the description to anchor | 5 descriptions truncated |
| 3 | Python `re.match` + `head + fm + tail` | `tail = m.group(3)` was just `\n---`, NOT the body. Body was silently dropped. | 5 files reduced to 4-line stubs (recovered via snapshot) |

After 3 failures, this v2 template solved it on the first try. The
canonical copy lives at
`~/.hermes-state/temp/2026-07-11/safe_patch_v2.py`.

## The template (key parts)

```python
def split_frontmatter(text):
    """Return (head, fm, closer, body).
    head:    '---\n' (or whatever opens the frontmatter)
    fm:      the YAML content between the markers
    closer:  '\n---' (the closing marker)
    body:    everything after the closer
    None values if frontmatter malformed.
    """
    m = re.match(r"^---\s*\n(.*?\n)---(\s*\n)?", text, re.DOTALL)
    if not m:
        return (None, None, None, None)
    head = "---\n"
    fm = m.group(1)
    after = text[m.end():]
    closer = "\n---"
    body = after  # everything after the closer
    return (head, fm, closer, body)


def insert_uses_after_name(fm, uses_value):
    """Insert `uses: [...]` as a new line right after the `name:` line.
    Returns (new_fm, was_modified).
    """
    if re.search(r"^uses:", fm, re.MULTILINE):
        return (fm, False)
    new_fm = re.sub(
        r"^(name:[^\n]*)$",
        rf"\1\nuses: {uses_value}",
        fm,
        count=1,
        flags=re.MULTILINE,
    )
    return (new_fm, new_fm != fm)


def main():
    for rel, uses_value in JOBS:
        snap_text = (SNAPSHOT / rel).read_text(encoding="utf-8")
        prod_text = (PROD / rel).read_text(encoding="utf-8")

        # Split snapshot and prod
        s_head, s_fm, s_closer, s_body = split_frontmatter(snap_text)
        p_head, p_fm, p_closer, p_body = split_frontmatter(prod_text)

        # Pre-check: snapshot and prod must have identical body and description
        if s_body != p_body:
            print(f"  ✗ {rel}: BODY differs from snapshot — production NOT at clean state")
            continue
        s_desc = extract_description(s_fm)
        p_desc = extract_description(p_fm)
        if s_desc != p_desc:
            print(f"  ✗ {rel}: frontmatter description differs — abort")
            continue

        # Build new frontmatter
        new_fm, modified = insert_uses_after_name(p_fm, uses_value)
        if not modified:
            continue

        # Construct new text — preserve head/closer/body exactly
        new_text = p_head + new_fm + p_closer + p_body  # body preserved!

        # Pre-write check: body byte-identical, description byte-identical
        n_head, n_fm, n_closer, n_body = split_frontmatter(new_text)
        if n_body != s_body:
            print(f"  ✗ {rel}: body changed in pre-write check — ABORT")
            continue
        if extract_description(n_fm) != s_desc:
            print(f"  ✗ {rel}: description changed in pre-write check — ABORT")
            continue

        # Write
        prod_path.write_text(new_text, encoding="utf-8")

        # Post-write re-read and verify
        post_text = prod_path.read_text(encoding="utf-8")
        post_head, post_fm, post_closer, post_body = split_frontmatter(post_text)
        if post_body != s_body:
            print(f"  ✗ {rel}: BODY CHANGED in post-write check — REVERTING")
            prod_path.write_text(snap_text, encoding="utf-8")
            continue
        if extract_description(post_fm) != s_desc:
            print(f"  ✗ {rel}: DESCRIPTION CHANGED in post-write check — REVERTING")
            prod_path.write_text(snap_text, encoding="utf-8")
            continue

        print(f"  ✓ {rel}")
```

## Key invariants the template enforces

1. **`body = text[m.end():]`, NOT `m.group(3)`.** This is pitfall #30's
   lesson. The regex capture group `\n---` is just the closer; the
   rest of the file lives in the substring after the full match.

2. **Construct `new_text = head + new_fm + closer + body`.** Head
   (`---\n`) opens, `new_fm` is the patched content, `closer` is
   `\n---`, `body` is everything after. Concatenating these in the
   right order is the only way to preserve the body.

3. **Verify body byte-identity at THREE checkpoints:** pre-write
   (against snapshot body), post-construct (against snapshot body),
   post-write (against snapshot body). If any one fails, revert.

4. **Snapshot first.** The template reads `SNAPSHOT / rel` and
   compares against it. The snapshot must exist before the script
   runs; create it via `cp <prod> <SNAPSHOT>/<rel>`.

5. **Pre-check that production is at clean state.** If
   `prod_text != snap_text` (modulo the new `uses:` line), abort.
   This catches the case where another agent already touched the
   file.

## When to use this template vs the patch tool

| Scenario | Use |
|---|---|
| Add a single line to frontmatter (e.g. `uses: [...]`) | **This template** |
| Add a line that doesn't exist in the current frontmatter shape (e.g. `requires:` was never declared) | **This template** |
| Edit an existing frontmatter value (e.g. change `version:`) | **This template** (insert after the line + re-verify) |
| Edit body markdown | `patch` tool, with FULL old_string |
| Insert a paragraph in body markdown | `patch` tool, with FULL old_string |
| Edit `~/.hermes/config.yaml` | **NEVER** — use `hermes config set` (pitfall #21) |

## What I learned that isn't in the code

1. **The first instinct was "use the patch tool"** — but the patch
   tool's fuzzy match is dangerous on YAML. Three rounds of failure
   proved this. The Python template is more verbose but more
   predictable.

2. **Verification must check every section, not just the section you
   intended to change.** Round 1's verification only checked
   `uses:` presence. The descriptions were already broken; the
   verification missed it. Round 4's verification checks description
   byte-identity AND body byte-identity AND `uses:` presence AND
   size delta. All four.

3. **Snapshot pre-edit is the safety net.** Every revert in rounds
   1-3 was a clean `cp <SNAPSHOT>/<rel> <PROD>/<rel>`. Without the
   snapshot, the failures would have been unrecoverable. **Always
   snapshot before any frontmatter edit.**

4. **The "ALL PASS" output can be a false positive.** Round 3's
   Python script reported "ALL 9 PASS" but the verification only
   checked the frontmatter, missing the body drop. The lesson:
   verify what you might have broken, not just what you intended to
   change.

## Companion references

- `references/consolidation-patterns-2026-07-11.md` — Pattern 27
  (the script that produced this template)
- `~/.hermes-state/snapshots/skill-uses-proposals__2026-07-11/` —
  the snapshot set that enabled safe revert in rounds 1-3
- `~/.hermes-state/temp/2026-07-11/safe_patch_v2.py` — the
  canonical working copy
- `~/.hermes-state/temp/2026-07-11/.skill-proposals-verified.csv`
  — the per-file verification report from the 2026-07-11 apply
  pass