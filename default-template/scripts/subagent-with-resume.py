#!/usr/bin/env python3
"""
subagent-with-resume.py — Resumable subagent-ish session dispatch with scratchpad carry-over.

HONEST SCOPE: This is NOT a true subagent dispatcher. The hermes-agent
runtime exposes `delegate_task` as an IN-SESSION tool only (callable by
the agent within its own tool budget); there is no `hermes delegate`
CLI subcommand. From a CLI script, the equivalent is `hermes chat
--source <tag> -q "<goal>"` which spawns a fresh chat session, not a
sub-process. We capture the session_id from the spawned chat and
resume via `hermes chat --resume <session_id> -q "<continue>"`.

This script therefore implements "resumable chat session with
scratchpad carry-over", which has the same resumability properties
as a subagent would (deterministic session_id, scratchpad state
preserved across attempts, automatic retry on failure) but uses
the chat surface rather than the in-session delegate_task tool.

Pattern (per user canon 2026-07-10 + 2026-07-12):
  1. Generate deterministic session_id from hash(goal + context_digest)
  2. Spawn `hermes chat --source subagent-<uid>` with the goal + scratchpad protocol
  3. If subagent fails (timeout, non-zero rc), READ prior scratchpad state
  4. Re-spawn with `--resume <session_id>` (continues the prior session) +
     inject prior scratchpad state as additional context
  5. Loop up to N retries with the SAME session_id (same scratchpad namespace)

Usage:
  python3 subagent-with-resume.py --goal "Research X" --context "..."
  python3 subagent-with-resume.py --goal "Research X" --context "..." --max-retries 5

Prereq:
  - `hermes` CLI on PATH
  - `mnemosyne_scratchpad_*` tools accessible (via the active hermes session)
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD_NS = "subagent"
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT_S = 600


def deterministic_id(goal: str, context: str) -> str:
    """Hash (goal + context_digest) to a stable 16-char hex."""
    digest = hashlib.sha256(f"{goal}|{context}".encode()).hexdigest()[:16]
    return f"{SCRATCHPAD_NS}-{digest}"


SCRATCHPAD_DB = (Path.home() / ".hermes" / "mnemosyne" / "data"
                  / "mnemosyne.db")


def _scratchpad_query(uid_prefix: str) -> list[dict]:
    """Read all scratchpad rows whose content starts with `uid_prefix`.

    The scratchpad is a flat table: id, content, session_id, created_at,
    updated_at. NOT a key-value store. Agents address entries by putting
    a key prefix in the content itself (e.g. 'subagent-<uid>/goal: ...').
    """
    try:
        import sqlite3
        if not SCRATCHPAD_DB.exists():
            return []
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        # Match either an exact-prefix match or a 'uid/sub_key' prefix in content
        cur.execute(
            "SELECT id, content, updated_at FROM scratchpad "
            "WHERE content LIKE ? OR content LIKE ? "
            "ORDER BY updated_at DESC",
            (f"{uid_prefix}%", f"{uid_prefix}/%"),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "content": r[1], "updated_at": r[2]}
            for r in rows
        ]
    except Exception as e:
        sys.stderr.write(f"[warn] scratchpad query failed: {e}\n")
        return []


def _scratchpad_write(uid: str, sub_key: str, content: str) -> bool:
    """Write a scratchpad entry with content prefixed by `uid/sub_key: ...`."""
    try:
        import sqlite3, uuid
        if not SCRATCHPAD_DB.parent.exists():
            SCRATCHPAD_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SCRATCHPAD_DB))
        cur = conn.cursor()
        entry_id = uuid.uuid4().hex[:16]
        full_content = f"{uid}/{sub_key}: {content}"
        cur.execute(
            "INSERT INTO scratchpad (id, content, session_id) VALUES (?, ?, ?)",
            (entry_id, full_content, "subagent-resume"),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        sys.stderr.write(f"[warn] scratchpad write failed: {e}\n")
        return False


def read_scratchpad(uid: str) -> str:
    """Read prior progress + final-state for this uid from the scratchpad DB.

    Addresses scratchpad entries by content-prefix (the actual scratchpad
    design: single-row table, agents tag entries via content prefix).
    """
    rows = _scratchpad_query(uid)
    if not rows:
        return "(no prior state)"
    parts = []
    for r in rows[:10]:  # cap to last 10 entries to avoid context blow-up
        # Strip the "uid/sub_key: " prefix for display
        content = r["content"]
        if content.startswith(f"{uid}/"):
            content = content[len(uid) + 1:]
        parts.append(f"### {r['updated_at']}\n{content}\n")
    return "\n".join(parts)


def dispatch_subagent(goal: str, context: str, uid: str,
                       prior_state: str, timeout_s: int,
                       attempt: int) -> tuple[bool, str, str]:
    """Spawn or resume hermes chat session with scratchpad protocol.

    Returns (success, output, session_id_or_empty).
    On attempt=1: spawn fresh chat, capture session_id from stdout.
    On attempt>1: --resume that session_id with prior scratchpad state.
    """
    full_goal = f"""{goal}

---

## Resumable session protocol (attempt {attempt})

You are session `{uid}`. Your scratchpad namespace is `mnemosyne_scratchpad_*`.

**SCRATCHPAD WRITE PROTOCOL** (mandatory):

1. **At start** (already done by wrapper): your goal is in `{uid}/goal`.

2. **Before each expensive tool call** (HTTP > 5s, model load, multi-file scan):
   ```
   mnemosyne_scratchpad_write("{uid}/progress/<step-name>",
     "<exact ID, path, URL, or fact you just discovered — verbatim, no summary>")
   ```

3. **Every 5 tool calls**: write a checkpoint:
   ```
   mnemosyne_scratchpad_write("{uid}/checkpoint-<count>",
     "completed: <list>; remaining: <list>; key_state: <exact IDs/paths>")
   ```

4. **Approaching your tool-call budget** (within 3 of max-turns=40):
   ```
   mnemosyne_scratchpad_write("{uid}/final-state",
     "goal: <the original task>, completed: <exact list>, remaining: <exact list>,
      resume_from: <exact IDs/paths/state needed to continue>")
   ```

5. **Before any tool call that might fail** (rate-limited API, network, server-down):
   checkpoint FIRST so the next retry has your prior progress even if this call kills you.

---

## Background context

{context}

---

## Prior state from previous attempt

{prior_state}
"""
    args = ["hermes", "chat",
            "-Q",                              # quiet mode for programmatic use
            "--accept-hooks",                   # skip interactive hook prompts
            "--checkpoints",                    # filesystem checkpoints for safety
            "--max-turns", "40",                 # per-attempt budget
            "--source", uid,                    # tags session with our deterministic id
            "--pass-session-id",                # emit session_id at end for capture
            "-q", full_goal]

    # If we have a session_id from a prior attempt, use --resume to continue it
    if hasattr(dispatch_subagent, "_session_id") and dispatch_subagent._session_id:
        args.extend(["--resume", dispatch_subagent._session_id])

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
        if proc.returncode == 0:
            sid = ""
            # Try to extract session id from the last "session ... id ..." line
            for line in proc.stdout.splitlines()[::-1]:
                line = line.strip()
                if line and "session" in line.lower():
                    import re
                    m = re.search(r"[a-f0-9]{8,}", line)
                    if m:
                        sid = m.group(0)
                        break
            if not sid:
                import re
                m = re.search(r"[a-f0-9]{16,}", proc.stdout)
                if m:
                    sid = m.group(0)
            if sid:
                dispatch_subagent._session_id = sid
            return True, proc.stdout, sid
        return False, f"hermes chat failed: rc={proc.returncode}, stderr={proc.stderr.strip()[:200]}", ""
    except subprocess.TimeoutExpired:
        return False, f"chat session timed out after {timeout_s}s (likely killed)", ""
    except FileNotFoundError:
        return False, "`hermes` CLI not found on PATH — install hermes-agent first", ""


def log_resume_attempt(uid: str, attempt: int, max_retries: int,
                        success: bool, error: str = "") -> None:
    """Append to a local audit log so you can see retry history."""
    log_path = Path.home() / ".hermes" / "logs" / "subagent-resume.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    status = "OK" if success else "FAIL"
    line = f"{ts} | {uid} | attempt={attempt}/{max_retries} | {status}"
    if error:
        line += f" | {error[:200]}"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Resumable subagent dispatch")
    p.add_argument("--goal", required=True, help="The subagent's task")
    p.add_argument("--context", default="",
                   help="Background context the subagent needs")
    p.add_argument("--max-retries", type=int, default=DEFAULT_RETRIES,
                   help=f"Max retry attempts (default {DEFAULT_RETRIES})")
    p.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S,
                   help=f"Per-attempt timeout in seconds (default {DEFAULT_TIMEOUT_S})")
    p.add_argument("--uid", default=None,
                   help="Override deterministic UID (default: hash(goal+context))")
    args = p.parse_args()

    uid = args.uid or deterministic_id(args.goal, args.context)
    print(f"[subagent] uid={uid}, max_retries={args.max_retries}, timeout={args.timeout_s}s")
    print(f"[subagent] goal: {args.goal[:120]}{'...' if len(args.goal) > 120 else ''}")
    print()

    # Write the goal to scratchpad on the very first run, so a future retry
    # that finds no in-flight subagent still has a "goal" entry to read.
    # Idempotent: only writes if no prior entry exists for this uid.
    prior_check = _scratchpad_query(uid)
    if not prior_check:
        _scratchpad_write(uid, "goal", f"goal={args.goal!r} context={args.context[:200]!r}")
        print(f"[subagent] wrote initial goal to scratchpad")

    prior_state = read_scratchpad(uid)
    print(f"[subagent] prior scratchpad state: {len(prior_state)} bytes")
    if "(no prior state)" in prior_state:
        print(f"[subagent] (first run — subagent will write scratchpad as it goes)")
    else:
        print(f"[subagent] (resuming — prior progress found in scratchpad)")
    print()

    for attempt in range(1, args.max_retries + 1):
        print(f"=== ATTEMPT {attempt}/{args.max_retries} ===")
        # Read fresh scratchpad state at each retry
        if attempt > 1:
            prior_state = read_scratchpad(uid)
            print(f"[subagent] re-read scratchpad: {len(prior_state)} bytes")

        success, output, sid = dispatch_subagent(
            args.goal, args.context, uid, prior_state, args.timeout_s, attempt
        )
        log_resume_attempt(uid, attempt, args.max_retries, success,
                            "" if success else output)

        if success:
            # Write the final output to scratchpad as final-state, so a future
            # retry can read it and know "the prior run completed with X".
            _scratchpad_write(uid, "final-state",
                              f"output={output[:500]!r} session_id={sid}")
            print(f"\n[subagent] SUCCESS on attempt {attempt}")
            if sid:
                print(f"[subagent] session_id: {sid}  (use 'hermes chat --resume {sid}' to continue later)")
            print(f"[subagent] output (first 500 chars):")
            print(output[:500])
            print(f"\n[subagent] full log: ~/.hermes/logs/subagent-resume.log")
            return 0

        # Failure: write a checkpoint to scratchpad so a retry can pick up.
        # The "in-flight" entry is the agent's hint that it was active.
        _scratchpad_write(uid, f"attempt-{attempt}-fail",
                          f"err={output[:200]!r}")
        print(f"[subagent] attempt {attempt} failed: {output[:200]}")
        if attempt < args.max_retries:
            print(f"[subagent] sleeping 5s before retry...")
            time.sleep(5)
        else:
            print(f"\n[subagent] all {args.max_retries} attempts failed")
            print(f"[subagent] check ~/.hermes/logs/subagent-resume.log for history")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())