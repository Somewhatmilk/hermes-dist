#!/usr/bin/env python3
"""
subagent-with-resume.py — Resumable subagent dispatch with scratchpad carry-over.

Pattern (per user canon 2026-07-10 + 2026-07-12):
  1. Generate deterministic subagent UUID from hash(goal + context_digest)
  2. Spawn subagent with scratchpad-write instructions in the goal
  3. If subagent gets killed/blocked/timeout, READ prior scratchpad state
  4. Re-dispatch with prior state as additional context
  5. Loop up to N retries with the SAME UUID (same scratchpad namespace)

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


def read_scratchpad(uid: str) -> str:
    """Read prior progress + final-state from scratchpad (via hermes CLI)."""
    parts = []
    for sub_key in ["goal", "progress", "final-state"]:
        full_key = f"{uid}/{sub_key}"
        try:
            out = subprocess.run(
                ["hermes", "mnemosyne", "scratchpad", "read", "--key", full_key],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode == 0 and out.stdout.strip():
                parts.append(f"### {sub_key}\n{out.stdout.strip()}\n")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return "\n".join(parts) if parts else "(no prior state)"


def dispatch_subagent(goal: str, context: str, uid: str,
                       prior_state: str, timeout_s: int) -> tuple[bool, str]:
    """Spawn subagent with scratchpad instructions + prior state in context."""
    full_context = f"""{context}

---

## Resumable subagent protocol

You are subagent `{uid}`. Your scratchpad namespace is `mnemosyne_scratchpad_*`.

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
     "completed: <list>; remaining: <list>; key state: <exact IDs/paths>")
   ```

4. **Approaching your tool-call budget** (within 3 of max_iterations=80):
   ```
   mnemosyne_scratchpad_write("{uid}/final-state",
     "goal: <the original task>, completed: <exact list>, remaining: <exact list>,
      resume_from: <exact IDs/paths/state needed to continue>")
   ```

5. **Before any tool call that might fail** (rate-limited API, network, server-down):
   checkpoint FIRST so the next retry has your prior progress even if this call kills you.

**WHEN YOUR PARENT RE-DISPATCHES YOU** (because your prior run got killed/blocked):

Read the prior state below to understand where you left off. Pick up from `resume_from` — do NOT redo work.

---

## Prior state from previous attempt

{prior_state}

---

Now execute the goal below. Use the scratchpad protocol throughout.

## Goal

{goal}
"""
    try:
        proc = subprocess.run(
            ["hermes", "delegate",
             "--goal", goal,
             "--context", full_context,
             "--max-iterations", "80",
             "--timeout", str(timeout_s)],
            capture_output=True, text=True, timeout=timeout_s + 30,
        )
        if proc.returncode == 0:
            return True, proc.stdout
        return False, f"hermes delegate failed: rc={proc.returncode}, stderr={proc.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return False, f"subagent timed out after {timeout_s}s (likely killed by parent timeout)"
    except FileNotFoundError:
        return False, "`hermes` CLI not found on PATH — install hermes-agent first"


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

        success, output = dispatch_subagent(
            args.goal, args.context, uid, prior_state, args.timeout_s
        )
        log_resume_attempt(uid, attempt, args.max_retries, success,
                            "" if success else output)

        if success:
            print(f"\n[subagent] SUCCESS on attempt {attempt}")
            print(f"[subagent] output (first 500 chars):")
            print(output[:500])
            print(f"\n[subagent] full log: ~/.hermes/logs/subagent-resume.log")
            return 0

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