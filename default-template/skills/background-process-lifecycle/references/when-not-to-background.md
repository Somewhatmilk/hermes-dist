# When NOT to use background=true

Background is the wrong choice when:

## 1. You need the result inline

If the next tool call depends on the output, use foreground `terminal()`. Background forces you to poll, which adds latency.

```python
# WRONG — wait, then poll, then read
launch = subprocess.run([...])  # background
sess_id = json.loads(launch.stdout)["session_id"]
# ... poll loop ...
log = subprocess.run([...])  # log
# finally have the data

# RIGHT — get it now
result = subprocess.run([...])  # foreground
data = result.stdout
```

## 2. You want the user to see the traceback on failure

If the command fails, foreground returns the traceback directly to the assistant turn. Background hides the failure unless you poll, and by the time you poll the user is already frustrated.

```python
# WRONG — silent failure, user waits
launch = subprocess.run([...])  # background, fails in 50ms
# ... 5 minutes pass, user asks "is it done?" ...
# now I discover the traceback

# RIGHT — immediate failure feedback
result = subprocess.run([...])  # foreground
if result.returncode != 0:
    print(f"FAILED: {result.stderr}")
    # user sees the traceback in the same turn
```

## 3. The command is fast

If a command takes < 5 seconds, use foreground. Background overhead (session_id allocation, process table entry, idle-TTL tracking) is wasted.

## 4. You need the result to choose the next action

```python
# WRONG — background, then poll, then decide
launch = subprocess.run([...])  # background
# ... poll until done ...
# now look at output to decide next step

# RIGHT — foreground, then decide
result = subprocess.run([...])  # foreground
if "ready" in result.stdout:
    do_thing_a()
else:
    do_thing_b()
```

## 5. The command is interactive

If the command reads from stdin (prompts, REPLs, password entry), foreground is required. Background + `process(action=submit)` works but is more complex than needed.

## 6. The user wants a service, not a session

If the daemon needs to survive:
- This turn AND every future turn → use a service manager (Task Scheduler, systemd, launchd, Docker restart policy)
- This turn and the next few turns → background is fine
- Only this turn → foreground

## 7. You're about to do batch work

If you have 10 commands to run and they don't depend on each other, use foreground with `&&` chaining. Backgrounding each one creates 10 session_ids to track.

## When foreground is the WRONG choice

- The process is a daemon and you want to track it for > 1 turn
- The process is a long-running watcher (file system events, log tail, kafka consumer)
- The process is a dev server you'll hit with HTTP from the next tool call
- The user explicitly says "keep it running" or "in the background" or "don't wait"
- The command will run for > 30s and you have other work to do in parallel

The decision rule:

```
Is the next tool call going to need the result inline? 
├─ YES → foreground
└─ NO  → Will the process need to outlive this turn?
         ├─ YES → background
         └─ NO  → foreground (overhead not worth it)
```
