#!/usr/bin/env python
"""Hermes Session-Open Inventory — verify tool presence with the 3-state trichotomy.

Usage:
    python verify_tool_installed.py --tool evolution
    python verify_tool_installed.py --tool hermes-cli
    python verify_tool_installed.py --all

Returns a report on stdout. Exit code 0 if all targets verified-present,
1 if any target is verified-absent or unverified (with a --strict flag).

This is the on-demand companion to the `hermes-session-open-inventory` skill.
Run it at session start, before any prompt-evolve invocation, and any time
memory claims a tool is installed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ---------- verified roots (live as of 2026-06-26) ----------

ROOTS = [
    Path(r"C:\Users\somew\AppData\Local\hermes"),
    Path(r"C:\Users\somew\AppData\Local\hermes\hermes-agent"),
    Path(r"C:\Users\somew\AppData\Local\hermes\hermes-agent-self-evolution"),
    Path(r"C:\Users\somew\Documents\hermes-research"),
    Path(r"C:\Users\somew\Downloads\One-Cut-Deeper"),
]

# ---------- needle table ----------

TOOL_TABLE = {
    "evolution": {
        "label": "GEPA / evolution.skills.evolve_skill",
        "needles": ["evolution"],
        "cli": [
            [r"C:\Users\somew\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
             "-m", "evolution.skills.evolve_skill", "--help"],
        ],
        "memory_query": "GEPA evolve_skill self-evolution",
    },
    "external_importers": {
        "label": "external_importers.py (GEPA scorer)",
        "needles": ["external_importers"],
        "cli": [],
        "memory_query": "external_importers RelevanceScorer",
    },
    "hermes-cli": {
        "label": "hermes CLI",
        "needles": [],
        "cli": [["hermes", "--version"]],
        "memory_query": "",
    },
    "mnemosyne": {
        "label": "Mnemosyne",
        "needles": ["mnemosyne"],
        "cli": [["hermes", "mnemosyne", "--help"]],
        "memory_query": "",
    },
    "dspy": {
        "label": "DSPy (in venv site-packages)",
        "needles": [r"site-packages\dspy"],
        "cli": [],
        "memory_query": "",
    },
    "gepa-standalone": {
        "label": "GEPA standalone library",
        "needles": [r"site-packages\gepa\gepa_utils"],
        "cli": [],
        "memory_query": "",
    },
}


# ---------- verification primitives ----------

def scan_roots(needles: Iterable[str]) -> list[Path]:
    """Return all files under any verified root whose name contains any needle.

    Performance: skip the node_modules / .git / venv site-packages subtrees unless
    the needle specifically targets one of them. A full rglob over the 91k-file
    hermes-agent/ tree takes >60s and rarely returns useful hits anyway.
    """
    if not needles:
        return []

    SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".pytest_cache", ".venv", "venv"}

    matches: list[Path] = []
    # Normalize needles to forward-slash form for portable substring matching
    needles_lc = [n.lower().replace("\\", "/") for n in needles]
    # site-packages needles are special: only scan those dirs
    site_pkg_only = all(("site-packages" in n) for n in needles_lc)

    for root in ROOTS:
        if not root.exists():
            continue
        try:
            if site_pkg_only:
                venv_sp = root / "hermes-agent" / "venv" / "Lib" / "site-packages"
                if venv_sp.exists():
                    for f in venv_sp.rglob("*"):
                        if not f.is_file():
                            continue
                        if any(n in str(f).lower().replace("\\", "/") for n in needles_lc):
                            matches.append(f)
                            if len(matches) > 50:
                                return list({str(m) for m in matches})[:20]
                continue

            # Otherwise: bounded walk, skip heavy dirs
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                # Cheap prune: skip any path under a SKIP_DIR
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                # Cheap name check first
                name_lc = f.name.lower()
                if any(n.split("/")[-1].split("\\")[-1] in name_lc for n in needles_lc):
                    matches.append(f)
                    if len(matches) > 50:
                        break
                else:
                    # Path-fragment check
                    f_lc = str(f).lower().replace("\\", "/")
                    if any(n in f_lc for n in needles_lc):
                        matches.append(f)
                        if len(matches) > 50:
                            break
        except (PermissionError, OSError):
            continue

    # dedup + cap
    seen = set()
    deduped: list[Path] = []
    for m in matches:
        s = str(m)
        if s in seen:
            continue
        seen.add(s)
        deduped.append(m)
    return deduped[:20]


def run_cli(cmd: list[str], timeout: int = 10) -> tuple[int | None, str]:
    """Run a CLI command; return (returncode, stdout+stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError as e:
        return None, f"FileNotFoundError: {e}"
    except subprocess.TimeoutExpired:
        return None, f"Timeout after {timeout}s"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def verify_tool(name: str) -> dict:
    """Verify a single tool. Returns a status dict."""
    spec = TOOL_TABLE.get(name)
    if not spec:
        return {
            "tool": name,
            "label": name,
            "state": "unknown",
            "evidence": [f"No entry in TOOL_TABLE for '{name}'"],
        }

    evidence: list[str] = []
    fs_hits: list[Path] = []
    cli_ok = False
    cli_results: list[str] = []

    # 1. Filesystem scan
    if spec["needles"]:
        fs_hits = scan_roots(spec["needles"])
        if fs_hits:
            evidence.append(f"FS: {len(fs_hits)} file(s) matched")
            for h in fs_hits[:5]:
                evidence.append(f"     {h}")
            if len(fs_hits) > 5:
                evidence.append(f"     ... and {len(fs_hits) - 5} more")
        else:
            evidence.append(f"FS: 0 matches across {len(ROOTS)} roots for needles {spec['needles']}")

    # 2. CLI verification
    for cmd in spec["cli"]:
        rc, out = run_cli(cmd)
        if rc == 0:
            cli_ok = True
            # First line of output is usually enough
            first = out.splitlines()[0] if out else "(empty)"
            cli_results.append(f"OK: {' '.join(cmd[:3])}... -> {first[:80]}")
        else:
            cli_results.append(f"FAIL(rc={rc}): {' '.join(cmd[:3])}... -> {out[:120]}")

    # 3. Decide state
    has_fs = len(fs_hits) > 0
    has_cli = cli_ok
    has_any_cli = len(spec["cli"]) > 0

    if has_fs and (has_cli or not has_any_cli):
        state = "verified_present"
    elif has_cli and not has_fs and has_any_cli:
        # CLI works but FS scan found nothing — entry-point only install
        state = "verified_present"
    elif has_fs and not has_cli and has_any_cli:
        state = "unverified"
    elif not has_fs and not has_cli:
        if not has_any_cli:
            state = "verified_absent"
        else:
            state = "verified_absent"
    else:
        state = "verified_absent"

    return {
        "tool": name,
        "label": spec["label"],
        "state": state,
        "evidence": evidence + [f"CLI: {r}" for r in cli_results],
        "memory_query": spec["memory_query"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hermes Session-Open Inventory — verify tool presence"
    )
    parser.add_argument(
        "--tool", "-t",
        help="Tool name to verify (e.g. 'evolution', 'hermes-cli'). Use --all to verify every known tool.",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Verify all known tools in TOOL_TABLE",
    )
    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="Exit 1 if any tool is verified-absent or unverified",
    )
    args = parser.parse_args()

    if not args.tool and not args.all:
        parser.error("specify --tool NAME or --all")

    if args.all:
        targets = list(TOOL_TABLE.keys())
    else:
        targets = [args.tool]

    from datetime import datetime
    print("=" * 70)
    print(f"SESSION-OPEN INVENTORY ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 70)
    print()

    states = {"verified_present": 0, "verified_absent": 0, "unverified": 0, "unknown": 0}
    for t in targets:
        r = verify_tool(t)
        state = r["state"]
        states[state] = states.get(state, 0) + 1
        # Symbol mapping
        sym = {
            "verified_present": "[OK]",
            "verified_absent": "[NO]",
            "unverified": "[??]",
            "unknown": "[??]",
        }.get(state, "[??]")
        print(f"{sym} {r['label']}  ->  {state}")
        for ev in r["evidence"]:
            print(f"      {ev}")
        if r.get("memory_query"):
            print(f"      memory_query: {r['memory_query']}")
        print()

    print("=" * 70)
    print(f"SUMMARY: present={states['verified_present']}  "
          f"absent={states['verified_absent']}  "
          f"unverified={states['unverified']}  "
          f"unknown={states['unknown']}")
    print("=" * 70)

    if args.strict and (states["verified_absent"] > 0 or states["unverified"] > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())