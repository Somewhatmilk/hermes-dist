#!/usr/bin/env python3
"""
smoke-kanban.py — One canonical smoke session for kanban worker dispatch.

Pattern (per design at ~/.hermes/issues/2026-07-12-smoke-test-consolidation.md):
  - Single, stable test kanban task for the kanban-worker dispatch smoke test
  - One canonical query set (3 queries)
  - Results written to Mnemosyne scratchpad

Usage:
  python3 ~/.hermes/scripts/smoke-kanban.py --run    # run the smoke (creates + completes a test task)
  python3 ~/.hermes/scripts/smoke-kanban.py --query  # query last result from scratchpad
"""
import argparse
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD_DB = Path.home() / ".hermes" / "mnemosyne" / "data" / "mnemosyne.db"
KANBAN_DB = Path.home() / ".hermes" / "kanban.db"
SMOKE_NS = "smoke-kanban"


def write_scratchpad(prefix: str, content: str) -> bool:
    try:
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        entry_id = uuid.uuid4().hex[:16]
        full_content = f"{prefix}: {content}"
        cur.execute(
            "INSERT INTO scratchpad (id, content, session_id) VALUES (?, ?, ?)",
            (entry_id, full_content, "smoke-kanban-runner")
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


def get_or_create_smoke_task() -> str | None:
    """Get the latest smoke-kanban task_id, or create a new one."""
    if not KANBAN_DB.exists():
        return None
    # Check scratchpad first
    last = read_scratchpad(f"{SMOKE_NS}/task_id")
    if last:
        # Extract task_id from "task_id=t_xxx"
        if "task_id=" in last:
            return last.split("task_id=")[1].split()[0].strip()
    # Create a new test task
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    task_id = f"smoke-kanban-{timestamp}-{uuid.uuid4().hex[:6]}"
    title = f"[smoke-kanban] {timestamp}"
    r = subprocess.run(
        ["hermes", "kanban", "create", "--title", title, "--description",
         "Synthetic smoke-test task. Created by smoke-kanban.py.",
         "--priority", "low", "--json"],
        capture_output=True, text=True, encoding='utf-8', timeout=30
    )
    if r.returncode == 0:
        # Parse task_id from JSON output
        import json
        try:
            data = json.loads(r.stdout)
            tid = data.get("id") or data.get("task_id")
            if tid:
                write_scratchpad(f"{SMOKE_NS}/task_id", f"task_id={tid} created={timestamp}")
                return tid
        except json.JSONDecodeError:
            # Fallback: search for t_ pattern in stdout
            import re
            m = re.search(r'(t_[a-f0-9]{8,})', r.stdout)
            if m:
                tid = m.group(1)
                write_scratchpad(f"{SMOKE_NS}/task_id", f"task_id={tid} created={timestamp}")
                return tid
    sys.stderr.write(f"[err] kanban create failed: {r.stderr[:200]}\n")
    return None


# Canonical query set for kanban worker dispatch
def run_smoke():
    task_id = get_or_create_smoke_task()
    if not task_id:
        print("smoke-kanban: could not get or create a test task. Aborting.")
        return
    print(f"smoke-kanban: using task_id={task_id}")
    results = {}

    # 1. Claim the task
    print(f"  step 1: claim")
    r = subprocess.run(
        ["hermes", "kanban", "claim", "--ttl", "60", task_id],
        capture_output=True, text=True, encoding='utf-8', timeout=15
    )
    results["claim"] = "OK" if r.returncode == 0 else f"FAIL: rc={r.returncode}"

    # 2. Complete the task
    print(f"  step 2: complete")
    r = subprocess.run(
        ["hermes", "kanban", "complete", task_id,
         "--result", "smoke OK",
         "--summary", f"Smoke test passed at {datetime.now(timezone.utc).isoformat()}"],
        capture_output=True, text=True, encoding='utf-8', timeout=15
    )
    results["complete"] = "OK" if r.returncode == 0 else f"FAIL: rc={r.returncode}"

    # 3. Show the task to confirm state
    print(f"  step 3: show task")
    r = subprocess.run(
        ["hermes", "kanban", "show", task_id, "--json"],
        capture_output=True, text=True, encoding='utf-8', timeout=15
    )
    if r.returncode == 0:
        # Extract status from JSON
        import json, re
        try:
            data = json.loads(r.stdout)
            status = data.get("status") or "?"
            results["show_status"] = status
        except json.JSONDecodeError:
            m = re.search(r'"status":\s*"([^"]+)"', r.stdout)
            results["show_status"] = m.group(1) if m else "unknown"
    else:
        results["show_status"] = f"FAIL: rc={r.returncode}"

    # Write results
    timestamp = datetime.now(timezone.utc).isoformat()
    write_scratchpad(f"{SMOKE_NS}/last_run", f"timestamp={timestamp} task_id={task_id}")
    for query_id, answer in results.items():
        write_scratchpad(f"{SMOKE_NS}/result/{query_id}", answer)

    print(f"\nsmoke-kanban: complete. {len(results)} results:")
    for k, v in results.items():
        print(f"  {k}: {v}")


def query_smoke():
    last = read_scratchpad(f"{SMOKE_NS}/last_run")
    if last is None:
        print("smoke-kanban: no prior run found. Run with --run first.")
        return
    print(f"Last smoke-kanban run:")
    print(f"  {last}")
    print()
    for query_id in ["claim", "complete", "show_status"]:
        result = read_scratchpad(f"{SMOKE_NS}/result/{query_id}")
        if result:
            print(f"  {query_id}:")
            print(f"    {result}")


def main():
    p = argparse.ArgumentParser(description="Smoke test for kanban worker dispatch")
    p.add_argument("--run", action="store_true", help="Run the smoke")
    p.add_argument("--query", action="store_true", help="Query last smoke result from scratchpad")
    p.add_argument("--reset", action="store_true", help="Clear prior smoke task_id")
    args = p.parse_args()

    if args.reset:
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        cur.execute("DELETE FROM scratchpad WHERE content LIKE ? OR content LIKE ?",
                    (f"{SMOKE_NS}/task_id:%", f"{SMOKE_NS}/result/%"))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        print(f"smoke-kanban: cleared {deleted} prior entries.")
        return

    if args.run:
        run_smoke()
    elif args.query:
        query_smoke()
    else:
        p.print_help()


if __name__ == "__main__":
    main()