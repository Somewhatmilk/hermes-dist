#!/usr/bin/env python3
"""Safe surgical patcher for SKILL.md frontmatter inserts.

Inserts a single `uses: [...]` line (or any field) after the `name:`
line in a SKILL.md file's YAML frontmatter, with byte-identity
verification of description and body at every checkpoint.

Threat tier: MEDIUM (real production touch, but designed to fail safely).

Usage:
    1. Snapshot files first:
         cp -r ~/.hermes/skills/<topic>/ ~/.hermes-state/snapshots/<topic>__<date>/
    2. Set JOBS list (source_skill_path, uses_value) below.
    3. Set SNAPSHOT and PROD paths.
    4. Run: python3 safe_patch_v2.py

Companion: pitfalls #28, #29, #30 in skill-library-consolidator.
Reference: references/safe-patch-v2-frontmatter-insert-2026-07-11.md
"""
import re
from pathlib import Path

# CONFIGURE THESE
SNAPSHOT = Path(r"C:\Users\somew\.hermes-state\snapshots\YOUR_TOPIC__2026-07-11\.hermes\skills")
PROD = Path.home() / ".hermes" / "skills"

# (relative_path_from_PROD, uses_value_to_insert)
JOBS = [
    # Example:
    # ("failures-journal/SKILL.md", "[hermes-session-open-inventory]"),
]


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


def extract_description(fm):
    """Extract description value from frontmatter content."""
    m = re.search(r"^description:\s*(.+?)\s*$", fm, re.MULTILINE)
    return m.group(1) if m else None


def insert_field_after_name(fm, field_name, field_value):
    """Insert `<field_name>: <field_value>` as a new line right after the `name:` line.

    Returns (new_fm, was_modified).
    Skips if the field already exists.
    """
    if re.search(rf"^{re.escape(field_name)}:", fm, re.MULTILINE):
        return (fm, False)
    new_fm = re.sub(
        r"^(name:[^\n]*)$",
        rf"\1\n{field_name}: {field_value}",
        fm,
        count=1,
        flags=re.MULTILINE,
    )
    return (new_fm, new_fm != fm)


def main():
    print("=== Safe frontmatter insert (v2) ===\n")
    for rel, field_name, field_value in JOBS:
        snap_path = SNAPSHOT / rel
        prod_path = PROD / rel

        snap_text = snap_path.read_text(encoding="utf-8")
        prod_text = prod_path.read_text(encoding="utf-8")

        # Split snapshot and prod
        s_head, s_fm, s_closer, s_body = split_frontmatter(snap_text)
        p_head, p_fm, p_closer, p_body = split_frontmatter(prod_text)

        if None in (s_head, s_fm, p_head, p_fm):
            print(f"  ✗ {rel}: frontmatter parse failure")
            continue

        # Pre-check 1: snapshot and prod must have identical body
        if s_body != p_body:
            print(f"  ✗ {rel}: BODY differs from snapshot — production NOT at clean state")
            print(f"      snap body len={len(s_body)}  prod body len={len(p_body)}")
            continue

        # Pre-check 2: description matches
        s_desc = extract_description(s_fm)
        p_desc = extract_description(p_fm)
        if s_desc != p_desc:
            print(f"  ✗ {rel}: frontmatter description differs — abort")
            continue

        # Build new frontmatter
        new_fm, modified = insert_field_after_name(p_fm, field_name, field_value)
        if not modified:
            print(f"  ? {rel}: not modified ({field_name}: already present)")
            continue

        # Construct new text — preserve head/closer/body exactly
        new_text = p_head + new_fm + p_closer + p_body

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
        print(f"      {field_name}: {field_value}")
        print(f"      body bytes preserved: {len(post_body)} (== {len(s_body)})")
        print(f"      description preserved: {s_desc[:60]}...")


if __name__ == "__main__":
    main()