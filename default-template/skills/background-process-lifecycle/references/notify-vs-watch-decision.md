# notify_on_complete vs watch_patterns — full decision tree

Two flags for `terminal(background=true)`. They control when the system pings you with an update.

## The flags

- **notify_on_complete=true**: system pings once when the process exits (any exit code)
- **watch_patterns=[regex, regex, ...]**: system pings when output matches any regex; subject to 15s strike limit and 3-strike auto-disable

## Decision tree

```
Does the process emit a "I'm ready" signal you can wait for?
├─ YES → wait_patterns=[that_signal_regex]
└─ NO  → Is the process bounded (will finish in finite time)?
         ├─ YES → notify_on_complete=true
         └─ NO  → BOTH (wait for ready, then notify on exit if you care)
```

## wait_patterns in detail

- `watch_patterns=[r"^.*ready.*$"]` — wait for "ready" in any line
- `watch_patterns=[r"^Bound to .*:(\d+)$", r"server ready"]` — multiple patterns
- Patterns are ERE regex (not PCRE) — escape `()[]{}` etc.
- Patterns are matched against the **combined stdout+stderr** stream
- A match pings you ONCE; you do not get re-pinged on subsequent matches of the same pattern
- 15s hard rate limit per process — if a pattern matches > every 15s, it's strike-limited
- 3 strikes → watch_patterns is **silently disabled for that session** with no notification

## The 15s strike limit — why it exists

The system uses watch_patterns for **rare mid-process signals** (server bound, kafka topic created, index build complete). If you put a pattern that matches every line of log output, the system pings you 100+ times in a minute and floods your context. The 15s rate limit prevents this.

## Common watch_patterns recipes

| Use case | Pattern | Notes |
|---|---|---|
| HTTP server ready | `r"^.*listening on .*:(\d+)$"` | match the bind line |
| Database ready | `r"ready to accept connections"` | postgres/mysql style |
| Build complete (vite) | `r"ready in \d+ ms"` | match the timing line |
| Build complete (next) | `r"compiled successfully"` | |
| Test suite done | `r"Tests:.*passed"` | jest/vitest |
| Migration done | `r"(Migration applied|Schema sync complete)"` | |
| Kafka topic created | `r"^.*topic .* created$"` | |
| Background job done | `r"job .* completed"` | |

## notify_on_complete in detail

- One ping per session, when the process exits
- The ping includes exit_code, total runtime, and last N lines of output
- Use this when: build, test suite, batch script, anything that has a defined end
- Don't use for daemons (they never exit naturally)

## notify AND watch together

For long-lived services, you may want both: wait for the ready signal so you can start using the service, AND get notified when it eventually exits (for crash detection):

```python
# terminal(background=true, command="...", notify_on_complete=true, watch_patterns=[r"ready"])
# - system pings you on "ready" line (one time)
# - system also pings you on process exit (one time)
# - you can use the ready signal to proceed with API calls
# - you can use the exit signal to detect crashes
```

## Anti-patterns

1. **watch_patterns for routine logs**: don't add `[r"INFO"]` or `[r"^.*$"]` — strikes out
2. **watch_patterns without escape**: pattern `r"ready ("` will fail to compile (unbalanced paren)
3. **notify_on_complete on daemons**: never fires because daemons don't exit naturally
4. **Both flags for short processes**: 1-second script with both flags = the system pings you twice for 1 second of work
5. **watch_patterns with no fallback**: if your pattern doesn't match, you'll never know — set a hard timeout via process(action=wait, timeout=N)

## Verifying your choice

Run this in a scratch session to see the actual pings:

```python
# short daemon for testing
import subprocess
# terminal(background=true, command="python -c 'import time; print(\"ready\"); time.sleep(30)'", watch_patterns=[r"ready"], notify_on_complete=true)
# observe:
#   - one ping when "ready" appears (~0.5s)
#   - one ping when the 30s sleep ends
# if you see only the ready ping and not the exit ping, watch_patterns is working
# if you see neither, your pattern is wrong
```

## When in doubt

Default to **notify_on_complete=true** with no watch_patterns. It is the safest choice: one ping when the process ends, no strike risk, works for every bounded task. Add watch_patterns only when you have a specific ready-signal you need to wait for.
