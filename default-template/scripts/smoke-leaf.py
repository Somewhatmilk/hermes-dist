#!/usr/bin/env python3
"""
smoke-leaf.py — One canonical smoke session for leaf-agent dispatch.

Pattern (per design at ~/.hermes/issues/2026-07-12-smoke-test-consolidation.md):
  - Single, stable session_id for the leaf-agent dispatch smoke test
  - One canonical query set (5 queries)
  - Results written to Mnemosyne scratchpad, NOT a fresh hermes chat per call
  - Verifier scripts query scratchpad instead of spawning sessions

Usage:
  python3 ~/.hermes/scripts/smoke-leaf.py --run   # run the smoke, write to scratchpad
  python3 ~/.hermes/scripts/smoke-leaf.py --query # query last result from scratchpad

The session_id convention is `smoke-leaf-{n}` where n increments per run.
The scratchpad prefix is `smoke-leaf/result-{n}`.
"""
import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD_DB = Path.home() / ".hermes" / "mnemosyne" / "data" / "mnemosyne.db"
SMOKE_NS = "smoke-leaf"


def get_or_create_session_id() -> str:
    """Get the latest smoke-leaf session_id from scratchpad, or create a new one.

    The session_id is stable across runs — once we've spawned one
    smoke-leaf session, we keep reusing its session_id for subsequent
    runs unless the user explicitly resets it.
    """
    import sqlite3
    if not SCRATCHPAD_DB.exists():
        return f"smoke-leaf-{uuid.uuid4().hex[:8]}"
    conn = sqlite3.connect(str(SCRATCHPAD_DB))
    cur = conn.cursor()
    # Find the latest smoke-leaf session_id from prior scratchpad entries
    cur.execute(
        "SELECT content FROM scratchpad WHERE content LIKE ? ORDER BY updated_at DESC LIMIT 1",
        (f"{SMOKE_NS}/session:%",)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        content = row[0]
        # Extract session_id from content
        if "session_id=" in content:
            return content.split("session_id=")[1].split()[0].strip()
    return f"smoke-leaf-{uuid.uuid4().hex[:8]}"


def write_scratchpad(prefix: str, content: str) -> bool:
    """Write a scratchpad entry."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        entry_id = uuid.uuid4().hex[:16]
        full_content = f"{prefix}: {content}"
        cur.execute(
            "INSERT INTO scratchpad (id, content, session_id) VALUES (?, ?, ?)",
            (entry_id, full_content, "smoke-leaf-runner")
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        sys.stderr.write(f"[err] scratchpad write failed: {e}\n")
        return False


def read_scratchpad(prefix: str) -> str | None:
    """Read the latest scratchpad entry with the given prefix."""
    import sqlite3
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


# Canonical query set for leaf-agent dispatch
CANONICAL_QUERIES = [
    ("session_id", "what is your session_id?"),
    ("model", "what model are you using? reply with just the model name"),
    ("config_check", "read ~/.hermes/config.yaml and report memory.mnemosyne.auto_sleep"),
    ("skills_count", "list files in ~/.hermes/skills/hermes/ and report the count"),
    ("env_var", "what is the value of MNEMOSYNE_VEC_WEIGHT in process env? reply with the value or 'unset'"),
]


def run_smoke():
    """Run the canonical query set against hermes chat --resume."""
    sid = get_or_create_session_id()
    print(f"smoke-leaf: using session_id={sid}")
    results = {}
    for query_id, query_text in CANONICAL_QUERIES:
        print(f"  query: {query_id} = '{query_text[:60]}...'")
        try:
            r = subprocess.run(
                ["hermes", "chat", "--resume", sid, "-q", query_text],
                capture_output=True, text=True, encoding='utf-8', timeout=60
            )
            if r.returncode == 0:
                # Take first line of stdout as the answer
                answer = r.stdout.strip().split("\n")[0][:200]
                results[query_id] = answer
                print(f"  answer: {answer[:100]}")
            else:
                results[query_id] = f"ERROR: rc={r.returncode} stderr={r.stderr[:100]}"
                print(f"  error: rc={r.returncode}")
        except subprocess.TimeoutExpired:
            results[query_id] = "ERROR: timeout"
            print(f"  error: timeout")
        except Exception as e:
            results[query_id] = f"ERROR: {e}"
            print(f"  error: {e}")

    # Write all results to scratchpad
    timestamp = datetime.now(timezone.utc).isoformat()
    session_record = f"session_id={sid} timestamp={timestamp} run_id={uuid.uuid4().hex[:8]}"
    write_scratchpad(f"{SMOKE_NS}/session", session_record)
    for query_id, answer in results.items():
        write_scratchpad(f"{SMOKE_NS}/result/{query_id}", answer)
    write_scratchpad(f"{SMOKE_NS}/last_run", f"timestamp={timestamp} sid={sid}")
    print(f"\nsmoke-leaf: complete. {len(results)} results written to scratchpad at {SMOKE_NS}/*")
    return results


def query_smoke():
    """Query the last smoke result from scratchpad."""
    last = read_scratchpad(f"{SMOKE_NS}/last_run")
    if last is None:
        print("smoke-leaf: no prior run found. Run with --run first.")
        return
    print(f"Last smoke-leaf run:")
    print(f"  {last}")
    print()
    for query_id, _ in CANONICAL_QUERIES:
        result = read_scratchpad(f"{SMOKE_NS}/result/{query_id}")
        if result:
            print(f"  {query_id}:")
            print(f"    {result}")
        else:
            print(f"  {query_id}: (not found)")


def main():
    p = argparse.ArgumentParser(description="Smoke test for leaf-agent dispatch")
    p.add_argument("--run", action="store_true", help="Run the smoke (spawns 1 hermes chat)")
    p.add_argument("--query", action="store_true", help="Query last smoke result from scratchpad")
    p.add_argument("--reset", action="store_true", help="Clear prior smoke session_id")
    args = p.parse_args()

    if args.reset:
        # Clear the smoke-leaf session record
        import sqlite3
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        cur.execute("DELETE FROM scratchpad WHERE content LIKE ? OR content LIKE ?",
                    (f"{SMOKE_NS}/session:%", f"{SMOKE_NS}/result/%"))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        print(f"smoke-leaf: cleared {deleted} prior entries. Next --run will create a fresh session_id.")
        return

    if args.run:
        run_smoke()
    elif args.query:
        query_smoke()
    else:
        p.print_help()


if __name__ == "__main__":
    main()