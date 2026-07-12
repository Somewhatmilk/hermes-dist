#!/usr/bin/env python3
"""
smoke-profile.py — One canonical smoke session for profile-routed agent dispatch.

Pattern (per design at ~/.hermes/issues/2026-07-12-smoke-test-consolidation.md):
  - Stable test session per profile (smoke-profile-{name})
  - One canonical query set per profile (3 queries)
  - Results written to Mnemosyne scratchpad

Usage:
  python3 ~/.hermes/scripts/smoke-profile.py --run --profile <name>    # run smoke for one profile
  python3 ~/.hermes/scripts/smoke-profile.py --query --profile <name>  # query last result
  python3 ~/.hermes/scripts/smoke-profile.py --run-all                # run all 8 profiles
"""
import argparse
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD_DB = Path.home() / ".hermes" / "mnemosyne" / "data" / "mnemosyne.db"
SMOKE_NS = "smoke-profile"

# Per the routing SKILL.md v3.1.0 auto-load
ALL_PROFILES = ["default", "adversary", "communicate-design", "model-merger",
                "prompt-engineering", "reviewer", "sandbox", "software-engineering"]


def write_scratchpad(prefix: str, content: str) -> bool:
    try:
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        entry_id = uuid.uuid4().hex[:16]
        full_content = f"{prefix}: {content}"
        cur.execute(
            "INSERT INTO scratchpad (id, content, session_id) VALUES (?, ?, ?)",
            (entry_id, full_content, "smoke-profile-runner")
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        sys.stderr.write(f"[err] scratchpad write failed: {e}\n")
        return False


def read_scratchpad(prefix: str) -> str | None:
    if not SCRATCHPAD_DB.exists():
        return None
    conn = sqlite3.connect(str(SCRATCHPAD_DB))
    cur = conn.cursor()
    cur.execute(
        "SELECT content, updated_at FROM scratchpad WHERE content LIKE ? ORDER BY updated_at DESC LIMIT 1",
        (f"{prefix}:%",)
    )
    row = cur.fetchone()
    conn.close()
    return f"{row[1]}: {row[0]}" if row else None


def get_or_create_session_id(profile: str) -> str:
    """Get or create a stable session_id for the given profile."""
    last = read_scratchpad(f"{SMOKE_NS}/{profile}/session")
    if last:
        if "session_id=" in last:
            return last.split("session_id=")[1].split()[0].strip()
    return f"smoke-profile-{profile}-{uuid.uuid4().hex[:8]}"


# Canonical query set per profile
CANONICAL_QUERIES = [
    ("profile", "what profile are you using? reply with just the profile name"),
    ("auto_load_skills", "what auto-load skills do you see? list them"),
    ("mnemosyne_count", "how many memories are in working_memory? use sqlite3 ~/.hermes/mnemosyne/data/mnemosyne.db"),
]


def run_smoke(profile: str):
    sid = get_or_create_session_id(profile)
    print(f"smoke-profile[{profile}]: using session_id={sid}")
    results = {}
    for query_id, query_text in CANONICAL_QUERIES:
        print(f"  query: {query_id}")
        try:
            r = subprocess.run(
                ["hermes", "chat", "--source", f"smoke-profile-{profile}",
                 "--resume", sid, "-q", query_text],
                capture_output=True, text=True, encoding='utf-8', timeout=60
            )
            if r.returncode == 0:
                answer = r.stdout.strip().split("\n")[0][:200]
                results[query_id] = answer
                print(f"    answer: {answer[:100]}")
            else:
                results[query_id] = f"ERROR: rc={r.returncode}"
                print(f"    error: rc={r.returncode}")
        except subprocess.TimeoutExpired:
            results[query_id] = "ERROR: timeout"
        except Exception as e:
            results[query_id] = f"ERROR: {e}"

    timestamp = datetime.now(timezone.utc).isoformat()
    write_scratchpad(f"{SMOKE_NS}/{profile}/session",
                     f"session_id={sid} timestamp={timestamp}")
    for query_id, answer in results.items():
        write_scratchpad(f"{SMOKE_NS}/{profile}/result/{query_id}", answer)
    write_scratchpad(f"{SMOKE_NS}/{profile}/last_run",
                     f"timestamp={timestamp} sid={sid}")
    print(f"smoke-profile[{profile}]: complete. {len(results)} results.")


def run_all():
    """Run smoke for all 8 profiles. Spawns one session per profile (not per query)."""
    print(f"smoke-profile: running for {len(ALL_PROFILES)} profiles")
    for profile in ALL_PROFILES:
        run_smoke(profile)
    print(f"\nsmoke-profile: all done. {len(ALL_PROFILES)} profiles tested.")


def query_smoke(profile: str):
    last = read_scratchpad(f"{SMOKE_NS}/{profile}/last_run")
    if last is None:
        print(f"smoke-profile[{profile}]: no prior run found.")
        return
    print(f"Last smoke-profile[{profile}] run:")
    print(f"  {last}")
    for query_id, _ in CANONICAL_QUERIES:
        result = read_scratchpad(f"{SMOKE_NS}/{profile}/result/{query_id}")
        if result:
            print(f"  {query_id}:")
            print(f"    {result}")


def main():
    p = argparse.ArgumentParser(description="Smoke test for profile-routed agent dispatch")
    p.add_argument("--run", action="store_true", help="Run the smoke")
    p.add_argument("--run-all", action="store_true", help="Run smoke for all 8 profiles")
    p.add_argument("--query", action="store_true", help="Query last smoke result")
    p.add_argument("--profile", help="Profile name (default/adversary/etc.)")
    p.add_argument("--reset", action="store_true", help="Clear prior smoke state")
    args = p.parse_args()

    if args.reset:
        profile = args.profile or "default"
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        cur.execute("DELETE FROM scratchpad WHERE content LIKE ?",
                    (f"{SMOKE_NS}/{profile}/%",))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        print(f"smoke-profile[{profile}]: cleared {deleted} prior entries.")
        return

    if args.run_all:
        run_all()
    elif args.run:
        if not args.profile:
            print("error: --profile required with --run")
            sys.exit(1)
        run_smoke(args.profile)
    elif args.query:
        if not args.profile:
            print("error: --profile required with --query")
            sys.exit(1)
        query_smoke(args.profile)
    else:
        p.print_help()


if __name__ == "__main__":
    main()