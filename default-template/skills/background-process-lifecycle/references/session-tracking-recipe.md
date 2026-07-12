# Session-Tracking Recipe — gateway daemon worked example

End-to-end example showing the full session_id capture, poll, kill, restart cycle for a long-running daemon (the Hermes gateway in this case). All examples use the MCP `terminal` and `process` tools.

## The pattern

```python
# Step 1: launch in background, capture session_id
import subprocess, json

# terminal(background=true) returns immediately:
# {"status": "ok", "session_id": "s_20260709_185347_abc123", "pid": 4242, ...}
launch = subprocess.run([...])  # terminal(background=true, command="hermes gateway start")
result = json.loads(launch.stdout)
sess_id = result["session_id"]
pid = result["pid"]

# Step 2: emit visibly AND save cross-turn
print(f"✓ gateway launched: session={sess_id} pid={pid}")
mnemosyne.scratchpad("active_sessions", {"gateway": sess_id, "pid": pid, "started": "2026-07-09T18:53:47Z"})

# Step 3: poll for readiness (with watch_patterns, or just check status)
import time
for attempt in range(30):  # 30 seconds
    poll = subprocess.run([...])  # process(action=poll, session_id=sess_id)
    poll_data = json.loads(poll.stdout)
    if poll_data.get("status") == "running" and "ready" in poll_data.get("last_output", "").lower():
        print("✓ gateway is ready")
        break
    time.sleep(1)
else:
    print("⚠ gateway didn't become ready in 30s; check logs")
    # Don't kill — give it more time or escalate

# Step 4: use it
requests.get("https://127.0.0.1:8642/api/v1/status")  # gateway responding

# Step 5: later, kill cleanly when done
subprocess.run([...])  # process(action=kill, session_id=sess_id)
```

## Common pitfalls

- **Don't background the wrong command**: if you `terminal(background=true, command="hermes gateway stop")` you'll get a session that exits immediately. Background only makes sense for processes that don't terminate on their own.
- **Don't lose the session_id**: a stray print or untracked variable means the process is unkillable except via OS-level `taskkill`.
- **Don't poll too aggressively**: 100ms polling saturates the framework. 1-5s is fine for readiness; longer is fine for "alive?" checks.
- **Don't skip the readiness check**: a daemon can be "running" in the process table but not yet accepting requests (still binding to port, still loading config). The poll's `last_output` field tells you.

## When the process dies unexpectedly

If `process(action=poll)` returns `status=done, exit_code=N` and N != 0, the process exited with an error. To diagnose:

1. `process(action=log, session_id=sess_id, limit=50, offset=-50)` — get the last 50 lines
2. Look for the actual error message (Python traceback, segfault, "config not found", etc.)
3. Fix the underlying issue, then re-launch

## Cross-turn survival checklist

When you background a process that needs to survive multiple agent turns:

- [ ] session_id in conversation history (printed in turn)
- [ ] session_id in Mnemosyne scratchpad (cross-turn persistent)
- [ ] PID saved to scratchpad (survives session-table purge)
- [ ] If the process is the gateway/daemon: ensure there's a session_keepalive heartbeat OR use a service-manager (Task Scheduler, systemd) instead
- [ ] Document the kill instructions in the same scratchpad entry: `process(action=kill, session_id=X)`
