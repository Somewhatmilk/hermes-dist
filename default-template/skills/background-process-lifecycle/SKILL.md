---
name: background-process-lifecycle
description: Launch and track long-running processes from the agent via terminal(background=true) when the user wants the gateway, a watcher, a dev server, or any process that should outlive the terminal call. Captures the session_id discipline, notify_on_complete vs watch_patterns decision, process action tracking (poll, wait, list, kill), and the Windows MSYS-detach trap. Fires when the user reports the agent stopped responding (session_id was lost or the wait threshold passed) or asks whether a process is still running. Trigger phrases include start in background, run async, keep it running, launch daemon, start the gateway, is it running, why did that stop, process died.
---

# Background Process Lifecycle (terminal(background=true))

The terminal() tool has a foreground default (blocks until the command exits, returns the output). For long-running processes (daemons, watchers, dev servers, anything that should outlive the agent call) use background=true to get a session_id immediately, then track the process with process() calls.

## When to use background=true

- Daemons that don't terminate on their own (gateway, broker, watchdog)
- Long watchers (log tail, file system event, kafka consumer)
- Dev servers you will hit with curl/requests from the next tool call
- Anything where you need to KEEP THE SESSION ALIVE after the call returns

Do NOT use background=true for: quick one-shot commands (use foreground, get output immediately), or commands that should fail loudly (you want the traceback in the foreground return).

## The session_id capture discipline (the #1 foot-gun)

terminal(background=true) returns immediately with a session_id field. Save the session_id. If you lose it, you cannot poll, kill, or check status — the process is orphaned in Hermes process table until the framework idle-TTL reclaims it.

The mistake: the user says start the gateway in background → I call terminal(background=true) → I move on without noting the session_id → 3 turns later I want to check if alive → no way to find it except process(action=list) to grep for it.

The right pattern:
1. print the session_id in the assistant turn output (so it is in conversation history)
2. for cross-turn survival, write to Mnemosyne scratchpad or set an OS env var or stash in a kanban ticket
3. for mission-critical daemons, also save the OS PID from tasklist after launch (process_id survives session-table purges)

## notify_on_complete vs watch_patterns (the other #1 foot-gun)

terminal(background=true) takes these notification flags:

- notify_on_complete=true — the system pings you ONCE when the process exits. Use for bounded tasks: builds, test suites, batch jobs, anything with a defined end. Default-and-correct for most uses.
- watch_patterns=[regex, regex] — the system pings you on a regex match against the process output stream. Use for long-lived daemons that emit a ready signal: gateway startup complete, server bound to port N, kafka topic created. Do NOT use for routine output (per-message, per-log-line) — the system has a 15s strike limit and 3 strikes auto-disables watch_patterns.

The mistake: watch_patterns=[INFO] on a verbose daemon → 100+ pings in 5 minutes → strike limit → watch auto-disabled → you get nothing → next turn the user says "i had to send a new input."

The right call by use case:

| Use case | notify | watch_patterns |
|---|---|---|
| Gateway daemon | optional | Gateway running, Listening on port — wait for ready signal |
| Dev server | no | compiled successfully, ready in — wait for ready |
| Build (npm/pnpm) | yes | no — just wait for completion |
| Test suite | yes | no — just wait for completion |
| Log tail / file watcher | no | use foreground tail -f, not background |

## process() actions — the tracking API

| action | When to use | Returns |
|---|---|---|
| list | Find all live background sessions, or one specific session by ID | session id, status, age, last output preview |
| poll | Get a status update on one session (no new output) | status, exit_code if done, running, last_output_at |
| log | Get the full or paginated output of one session (offset/limit args for long output) | raw stdout/stderr text |
| wait | Block until the process exits or a timeout (uses the configured wait bound from mcp_discovery_timeout default 1.5s, or an explicit arg) | status done, exit_code |
| kill | Terminate the process by session_id | confirmation |
| close | Close stdin (not terminate) | n/a |
| submit | Send data + Enter to stdin (for answering prompts, e.g. pass passphrase) | n/a |

process(action=wait) is the right way to block until done without using notify. Use it for one-off bounded background tasks where you want to read the result inline.

## The Windows MSYS-detach trap

On Windows MSYS/Cygwin bash, shelling out with & does NOT reliably detach:

WRONG — may not detach cleanly; process can be reaped when bash exits:
```
terminal(command="python server.py &")  # foreground returns but child dies
```

Right way: use terminal(background=true) MCP primitive directly. The framework detach is real (uses job objects + CREATE_NEW_PROCESS_GROUP on Windows). The & shell trick is unreliable on Windows.

If the user is on Mac/Linux, nohup ... & is fine. If on Windows, use terminal(background=true).

## The "i had to send a new input" failure

If the user reports the agent "stopped" or "isn't responding", the cause is usually one of:

1. Process died but you did not poll — process(action=list) will show status=done
2. Process is alive but blocked on stdin — process(action=log) will show it stopped emitting output mid-line; use process(action=submit) to send a newline or the answer
3. watch_patterns strike-limited — already in the kill state, no more pings
4. Session idle-TTL reaped — the process was killed by Hermes background-process TTL. This is real and silent: the framework reclaims idle sessions after a timeout (typically 30+ min). The session_id is still valid for process() calls but the OS process is gone
5. Notify-on-complete hit and you missed it — the system pings once on exit, but if you were not in a turn that received the ping, you might miss it. Use process(action=list) to find done-sessions and log to read the final output

The first thing to do when the user says "i had to send a new input" is process(action=list) to see what background sessions are alive, and process(action=log) on the relevant one to see what it last emitted.

## Cross-platform shell-detach snippet (when background=true is unavailable)

If the MCP terminal is gated out and you only have foreground terminal, you can still launch a long-running process from a shell script that uses nohup + disown:

```
nohup python server.py > /tmp/server.log 2>&1 &
disown
```

On Windows MSYS, prefer:
```
MSYS_NO_PATHCONV=1 start //B python server.py
```

start //B runs a process detached (no console window spawned). After it returns, the Python process is independent. Save the PID from tasklist /FI IMAGENAME eq python.exe | head for tracking.

## Anti-pattern: lost the session_id

If you start a background process and do not preserve the session_id anywhere, you have:

- A live process on the OS
- No way for the agent to find it later except process(action=list) to grep by age
- After idle-TTL reclaim, the process is gone and you have no audit trail

Always emit the session_id visibly in the assistant turn (echo background session: {sess_id}), so it is in the conversation history. For long-lived daemons, ALSO write to a scratchpad or env var. For mission-critical processes (gateway, daemon), also save the PID from tasklist after launch — process_id is the OS-level handle that survives session-table purges.

## References

- references/session-tracking-recipe.md — end-to-end example: launch gateway, save session_id, poll, kill
- references/when-not-to-background.md — the cases where background is the WRONG choice (scripting, one-shots, anything where the user wants the result inline)
- references/notify-vs-watch-decision.md — the full decision tree for choosing the notification flag

## When NOT to use this skill

If you just need to run a quick command and get the output, use terminal() foreground — no need to background. Background is for processes that need to outlive the call. If you are about to start a daemon, ask: is there a service-manager way to run this? (Windows Task Scheduler, systemd, launchd, Docker) — those are more reliable than background terminal sessions.
