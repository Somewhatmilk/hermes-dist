#!/usr/bin/env python3
"""
scan_skill.py — scan a skill's files against the denylist.
Used by post-skill-create.sh. Returns:
  exit 0 = clean
  exit 1 = flagged (writes reason to stdout)
  exit 2 = error

Usage: scan_skill.py <denylist.yaml> <skill_dir>
"""
import re
import sys
import os
from pathlib import Path


def parse_yaml_list(path: Path, key: str) -> list[str]:
    """Extract a list under a top-level key from a YAML file (simple format)."""
    in_block = False
    items = []
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        if line.startswith(f"{key}:"):
            in_block = True
            continue
        if in_block and re.match(r"^[a-z_]+:", line):
            break
        if not in_block:
            continue
        # Drop in-line comments
        line = re.sub(r"#.*$", "", line)
        # Strip leading "- " and surrounding quotes
        m = re.match(r'^\s*-\s*"?([^"]+?)"?\s*$', line)
        if m:
            items.append(m.group(1))
    return items


def main():
    if len(sys.argv) != 3:
        print("Usage: scan_skill.py <denylist> <skill_dir>", file=sys.stderr)
        sys.exit(2)

    denylist_path = Path(sys.argv[1])
    skill_dir = Path(sys.argv[2])

    if not denylist_path.exists():
        print(f"denylist not found: {denylist_path}", file=sys.stderr)
        sys.exit(2)

    if not skill_dir.is_dir():
        print(f"skill dir not found: {skill_dir}", file=sys.stderr)
        sys.exit(2)

    # Parse all relevant denylist categories
    patterns = {
        "script_imports": parse_yaml_list(denylist_path, "script_imports"),
        "script_calls": parse_yaml_list(denylist_path, "script_calls"),
        "script_strings": parse_yaml_list(denylist_path, "script_strings"),
    }

    flagged = []

    # Scan SKILL.md for prompt-injection patterns in script_strings
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns["script_strings"]:
            try:
                if re.search(pattern, content):
                    flagged.append(f"SKILL.md:script_strings:{pattern}")
            except re.error:
                pass

    # Scan any bundled scripts
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in scripts_dir.iterdir():
            if not script.is_file():
                continue
            try:
                content = script.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for category in ("script_imports", "script_calls", "script_strings"):
                for pattern in patterns[category]:
                    try:
                        if re.search(pattern, content):
                            flagged.append(f"{script.name}:{category}:{pattern}")
                    except re.error:
                        pass

    if flagged:
        for f in flagged:
            print(f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
