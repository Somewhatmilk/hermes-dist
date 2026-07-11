#!/usr/bin/env python3
"""Skill library survey — re-runnable count + contradiction scan.

Writes one row per run to
~/.hermes/data-journal/telemetry/skill-library-consolidation-YYYY-MM.jsonl
and prints a summary to stdout.

Usage: python3 survey.py [--skills-root PATH] [--no-log]

Design notes:
  - Filters out .hub/ internals and node_modules/ to avoid double-counting
    bundled/shadowed skills.
  - "Unused" is view_count==0 AND use_count==0 from .usage.json. The cross-check
    against cron/SOUL references is NOT done here (see skill pitfall #1).
  - "Catalog ghost" = entry exists in .usage.json but no SKILL.md on disk.
    Ghost detection MUST use the frontmatter `name:` field, NOT the folder
    name (see pitfall #10 — 2026-07-04 false-positive failure).
  - "Stale" = last_viewed_at or last_used_at > 60d ago. (Note: post 2026-06-21
    bulk-import, this filter is meaningless for the first 60 days.)
  - Contradiction detection uses noun-phrase clustering on the frontmatter
    `description:` field. False-positive patterns (platform tags, product
    names, sibling tools, lifecycle stages) are NOT auto-classified — that's
    a human judgment; the script just lists clusters.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Domain tokens (skip these — too generic for contradiction detection)
STOP = {
    "the", "a", "an", "of", "to", "for", "and", "or", "with", "when", "use",
    "when", "if", "this", "that", "be", "is", "are", "by", "on", "in", "at",
    "as", "it", "its", "from", "but", "not", "skill", "skills", "file", "files",
    "content", "output", "input", "session", "sessions", "agent", "model",
    "tool", "tools", "cli", "api", "data", "step", "steps", "format", "rule",
    "rules",
}


def get_desc(p: Path) -> str | None:
    """Extract `description:` from a SKILL.md frontmatter block."""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    d = re.search(r"^description:\s*[\"']?(.*?)[\"']?\s*$", fm, re.MULTILINE)
    return d.group(1).strip() if d else None


def get_frontmatter_name(p: Path) -> str | None:
    """Extract `name:` from a SKILL.md frontmatter block.

    This is the canonical skill identifier. The folder name can differ
    (e.g., `mlops/models/audiocraft/SKILL.md` has `name: audiocraft-audio-generation`),
    and the catalog key in .usage.json matches the frontmatter name, not the folder.
    Using folder name for ghost detection produces false positives — see pitfall #10.
    """
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    nm = re.search(r"^name:\s*([\w\-./]+)", m.group(1), re.MULTILINE)
    return nm.group(1).strip() if nm else None


def extract_phrases(desc: str) -> set[str]:
    """Pull noun phrases from a description. Backticked names are most reliable;
    capitalized 1-3 word phrases are the fallback."""
    if not desc:
        return set()
    found = set()
    for m in re.finditer(r"`([^`]+)`", desc):
        ph = m.group(1).lower().strip()
        if 3 < len(ph) < 30 and not any(s in ph for s in STOP):
            found.add(ph)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", desc):
        ph = m.group(1).lower()
        words = ph.split()
        if 1 <= len(words) <= 3 and all(w not in STOP for w in words):
            found.add(ph)
    return found


def survey(skills_root: Path) -> dict:
    """Run the full survey. Returns a dict suitable for auto-log + stdout."""
    now = datetime.now(timezone.utc)
    usage_path = skills_root / ".usage.json"
    usage = json.loads(usage_path.read_text()) if usage_path.exists() else {}

    # 1. Enumerate skills on disk
    skill_files = [
        p for p in skills_root.rglob("SKILL.md")
        if ".hub" not in p.parts and "node_modules" not in p.parts
    ]

    # 2. Description lookup
    descs = {p.parent.name: get_desc(p) for p in skill_files}

    # 3. Usage stats
    unused_set = {
        n for n, s in usage.items()
        if s.get("view_count", 0) == 0 and s.get("use_count", 0) == 0
    }
    # CRITICAL: ghost detection must use the frontmatter `name:` field,
    # NOT the folder name. Many skills live in folders like
    # `mlops/models/audiocraft/` but declare `name: audiocraft-audio-generation`
    # in their frontmatter — the catalog key matches the frontmatter name,
    # not the folder. Using p.parent.name here produced 4 false positives
    # out of 5 in the 2026-07-04 survey (audiocraft-audio-generation,
    # evaluating-llms-harness, segment-anything-model, serving-llms-vllm).
    # See pitfall #10.
    on_disk_frontmatter_names: dict[str, Path] = {}
    for p in skill_files:
        nm = get_frontmatter_name(p)
        if nm:
            on_disk_frontmatter_names[nm] = p
    on_disk_unused = sorted(unused_set & set(on_disk_frontmatter_names.keys()))
    catalog_ghosts = sorted(unused_set - set(on_disk_frontmatter_names.keys()))

    stale_60 = []
    for n, s in usage.items():
        last = s.get("last_viewed_at") or s.get("last_used_at")
        if not last:
            continue
        try:
            dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - dt).days > 60:
            stale_60.append((n, (now - dt).days))

    # 4. Top-10 largest
    files_sorted = sorted(skill_files, key=lambda p: -p.stat().st_size)[:10]

    # 5. Category distribution
    cat_counts = Counter(p.relative_to(skills_root).parts[0] for p in skill_files)

    # 6. Noun-phrase clusters (potential contradictions)
    phrase_to_skills = defaultdict(list)
    for p in skill_files:
        desc = descs.get(p.parent.name)
        if not desc:
            continue
        for ph in extract_phrases(desc):
            phrase_to_skills[ph].append(p.parent.name)
    # Only clusters of 3+ unique skills
    clusters = {
        ph: sorted(set(sk))
        for ph, sk in phrase_to_skills.items()
        if len(set(sk)) >= 3
    }

    return {
        "ts": now.isoformat(),
        "skill_count": len(skill_files),
        "catalog_entries": len(usage),
        "pinned": sum(1 for s in usage.values() if s.get("pinned")),
        "catalog_ghosts": catalog_ghosts,
        "unused_on_disk": on_disk_unused,
        "stale_60d": [(n, d) for n, d in stale_60],
        "top_10_largest": [
            {"bytes": p.stat().st_size, "path": p.relative_to(skills_root).as_posix()}
            for p in files_sorted
        ],
        "category_counts": dict(cat_counts.most_common()),
        "phrase_clusters": clusters,
    }


def print_summary(r: dict) -> None:
    print(f"=== SKILL LIBRARY SURVEY ({r['ts']}) ===")
    print(f"  Skills on disk:        {r['skill_count']:>5}")
    print(f"  Catalog entries:       {r['catalog_entries']:>5}")
    print(f"  Pinned:                {r['pinned']:>5}")
    print(f"  Catalog ghosts:        {len(r['catalog_ghosts']):>5}  (in .usage.json, no SKILL.md)")
    print(f"  Unused (on disk):      {len(r['unused_on_disk']):>5}  (view=0 AND use=0)")
    print(f"  Stale (>60d):          {len(r['stale_60d']):>5}")
    print(f"  Categories:            {len(r['category_counts']):>5}")
    print(f"  Noun-phrase clusters:  {len(r['phrase_clusters']):>5}  (3+ skills share a phrase)")
    print()
    print("  TOP-10 LARGEST (refactor candidates):")
    for f in r["top_10_largest"]:
        print(f"    {f['bytes']:>7,} bytes  {f['path']}")
    print()
    print("  CATEGORY DISTRIBUTION (top 10):")
    for cat, n in list(r["category_counts"].items())[:10]:
        print(f"    {n:>3d}  {cat}/")
    print()
    print("  NOUN-PHRASE CLUSTERS (top 10 by size):")
    sorted_clusters = sorted(r["phrase_clusters"].items(),
                             key=lambda x: -len(x[1]))[:10]
    for ph, skills in sorted_clusters:
        sample = ", ".join(skills[:5])
        more = "..." if len(skills) > 5 else ""
        print(f"    '{ph}' ({len(skills)}): {sample}{more}")


def auto_log(r: dict, log_root: Path) -> Path:
    log_dir = log_root / "data-journal" / "telemetry"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"skill-library-consolidation-{r['ts'][:7]}.jsonl"
    # Strip the phrase_clusters from the row — keep it as a count for
    # longitudinal tracking; the full list goes to scratchpad if needed.
    row = {k: v for k, v in r.items() if k != "phrase_clusters"}
    row["phrase_cluster_count"] = len(r["phrase_clusters"])
    row["status"] = "survey-only"
    with open(log_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    return log_path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--skills-root",
        type=Path,
        default=Path.home() / ".hermes/skills",
        help="Path to the skills root (default: ~/.hermes/skills)",
    )
    ap.add_argument(
        "--no-log",
        action="store_true",
        help="Skip writing the auto-log row (data-journal)",
    )
    args = ap.parse_args()

    r = survey(args.skills_root)
    print_summary(r)

    if not args.no_log:
        log_path = auto_log(r, args.skills_root.parent)
        print()
        print(f"  Logged: {log_path}")


if __name__ == "__main__":
    main()