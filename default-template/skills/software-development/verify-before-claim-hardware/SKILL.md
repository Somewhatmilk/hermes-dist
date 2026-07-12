---
name: verify-before-claim-hardware
description: "Universal 'verify before claiming' discipline for any state-claim about hardware, services, containers, or files. Use when the user asks about hardware/peripheral/display/network/process state, OR when a tool/page/script/HTML/dashboard depends on data files that should exist, OR when the user reports something 'broken' that you haven't actually verified. Skip when: the user has given an exact command output to interpret. Triggers: 'is X working', 'why does X fail', 'I plugged in', 'I set up', 'I configured', 'I started', 'check if X is running'. The 5-step verification reflex + 12 universal anti-patterns. v0.4.8 trimmed to ~15 KB from 40 KB."
version: 1.4.0
author: Hermes Agent (default profile, derived from multi-session hardware/service diagnostics 2026-04 through 2026-07)
license: MIT
platforms: [any]
metadata:
  hermes:
    tags: [verify, hardware, services, containers, diagnostics, anti-hallucination, cross-validation]
    category: software-development
    related_skills: [diagnose-root-cause, hermes-llm-preflight, hermes-misbehavior-diagnosis, self-contained-spa-html]
    config: []
---

# verify-before-claim-hardware

## The rule

**Run the system detection command FIRST, before forming any hypothesis or explanation.**

The user's description of what they did is NEVER sufficient evidence. Users miscount cables, misremember ports, describe what they INTENDED to do as what they ACTUALLY did. The detection command is ground truth.

**Cross-reference at least 2 independent data sources** before stating root cause. If 2/3 agree, the picture is solid. If they disagree, you have a real diagnostic question, not a story to tell.

## When to use

ANY of these trigger conditions:
- user asks about display / monitor / cable / connector / port state
- user asks about GPU / video / driver / VRAM / nvidia-smi
- user asks about USB / audio / Bluetooth / network devices
- user asks about a running service / process / scheduled task
- user asks about container health / docker stack / compose status
- user asks about gateway / endpoint / port-bound service availability
- user asks "what tools/services do I have running" or similar
- user asks about a file that "should exist" (config, secret, watchdog script)
- user describes something that "should be" working but isn't
- user says "I did X, why doesn't it work"
- the user uses words like "I plugged in", "I set up", "I configured", "it's connected"
- **user reports a tool/page/script/HTML/dashboard "is broken" or shows a fetch/load error**
- **code being diagnosed declares fetches / imports / dependencies** — `ls` the target path before forming hypothesis

The "verify" reflex applies to **infra and services** as much as hardware. A user saying "I have searxng + camofox + llama-swap on this machine" is no more proof than "I plugged in the cable." Containers exit, ports get rebound, watchdogs die, files get moved. **Run the live check first.**

## The 5-step reflex (universal)

When the user reports a state-mismatch (something "should work" but doesn't):

1. **`ls` / `test -f` every file the code depends on.** Most "fetch failed" errors in browser JS are 404s on a single missing file — not protocol, not CORS, not file:// blocks. The error message does not tell you which file.

2. **Read the code, list every URL/import/dependency.** Don't trust the user's narrative description. The code is the contract.

3. **SIBLING-COMPARISON diagnostic.** If the user says "X is broken but Y works fine", diff them. What's different? Same path? Same auth? Same version? The difference is your lead.

4. **Probe before claiming.** A 1-second `curl -I` or `ls` is 100x cheaper than committing to a hypothesis. Probe FIRST, then form hypothesis.

5. **Quote the actual command output** that supports your conclusion. If you can't quote the output, you haven't verified — you've guessed.

## Common diagnostic commands (Windows)

```powershell
# Displays
Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorConnectionParams  # what tech each monitor uses
Get-PnpDevice -Class Monitor  # PnP view
[System.Windows.Forms.Screen]::AllScreens  # what user sees

# GPU
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
nvidia-smi -q  # full dump
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv  # what's using VRAM

# USB
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match "USB\\" }
# billboard device = USB-C alt mode refused
Get-CimInstance -Namespace root\wmi -ClassName "Win32_USBControllerDevice"  # USB device tree

# Processes / services
Get-Process | Where-Object { $_.Name -match "llama|swap" }
Get-CimInstance Win32_Process -Filter "name='llama-server.exe'" | Select ProcessId,ParentProcessId
Get-ScheduledTask | Where-Object { $_.TaskName -match "llama|hermes" }
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"

# Network
Get-NetAdapter | Format-Table Name,Status,LinkSpeed
Test-NetConnection -ComputerName <host> -Port <port>
netstat -ano | findstr LISTENING

# Storage / files
Get-ChildItem -Recurse | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-1) }
```

## Service / Container / Gateway Diagnostics

```bash
# Docker — what's actually running vs exited
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker inspect <container> --format '{{.State.Status}} {{.State.ExitCode}} {{.State.Error}}'
docker logs <container> --tail 50

# Compose — check the project state (not just container names; container_name can collide)
docker compose -f <path>/docker-compose.yml --project-name <name> ps -a

# Gateway health — curl, don't trust your memory of "I started it earlier"
curl -fsS http://127.0.0.1:<port>/health  # llama-swap, searxng, firecrawl all expose this
curl -s http://127.0.0.1:<port>/v1/models | jq '.data[].id'  # OpenAI-compat endpoints

# File existence — don't reason from a previous session's memory
ls -la "/c/Users/<user>/llama.cpp/" | grep -iE "watchdog|hidden|vbs|bat$"
test -f "/c/Users/<user>/.config/gcloud/hermes-sa.json" && echo OK || echo MISSING
```

**Pitfall: stale bind-mounts fail with cryptic OCI errors, not "file not found."** When a docker-compose service's bind-mount host path no longer exists, the container exits with code 127 and the error looks like:
```
error mounting ".../host/path" to rootfs at "/etc/<service>/<file>":
  not a directory: Are you trying to mount a directory onto a file (or vice-versa)?
```
This is NOT the service's fault — it's the host path being wrong. `docker inspect <name> --format '{{.State.Error}}'` shows the bind-mount source.

**Pitfall: "container is Up" ≠ "container is healthy."** A container in `Up` state with `health: starting` or no healthcheck hasn't finished initializing. Probe the actual endpoint (`curl /healthz`) before assuming it's serving traffic.

**Pitfall: agent-assumed stack state rots.** Across reboots or new sessions, the container set, port bindings, and running processes drift. The agent MUST re-run `docker ps -a` at session start for any infra question, the same way it re-runs `nvidia-smi` for GPU questions. Cached assumptions ("you have camofox on :9377") have a half-life measured in days, not weeks.

## The 3 reflexes (the cheap diagnostics that catch 80% of state-mismatch)

### 1. The "ls before forming hypothesis" reflex

The trigger: a user reports a browser page, dashboard, or local script fails with a fetch/load/import error, OR something "should work" but doesn't. Reflex: **before assuming a protocol issue, network block, or permission problem, `ls` (or `curl -I`) every file the code depends on.**

Most "fetch failed" errors in browser JS are 404s on a single missing file — not protocol, not CORS, not file:// blocks. The error message does not tell you which file. You have to find out by enumerating the code's URL/path dependencies and checking each.

### 2. The sibling-comparison diagnostic (the "what's different?" test)

When the user says "X is broken but Y works fine", diff them. Same path? Same auth? Same version? The difference is your lead. Often the "broken" thing has a missing dependency the "working" thing has — or vice versa.

### 3. The "fetch failed" message is misleading (browser JS)

When `fetch(url).catch(err => ...)` triggers, the error message is almost always "TypeError: Failed to fetch" — regardless of whether the real cause is 404, 500, DNS failure, CORS rejection, mixed-content block, or a sibling-Promise rejection. The error message does not tell you which. The diagnostic procedure:
1. Read the code: list every URL being fetched.
2. `ls`/`curl -I` each URL — which one is 404/500/empty?
3. Fix that one. The error message does not tell you which.

**Don't** assume file:// blocks (only true for `fetch` from a `file://` HTML page); **don't** assume CORS (only true for cross-origin `fetch` with custom headers); **don't** assume "the user needs to start a server" (only true if no other HTTP server is serving the data and the page is file://). The 80% case is a single missing file in a `Promise.all` dependency list. The other 20% is a typo in the URL path.

## When a previous agent's note contradicts the current state

A previous agent wrote a Mnemosyne row saying X. User explicitly said X is wrong. **The right move is invalidate the memory row and obey**, not defend the prior agent's note.

The user is closer to the live state than the previous agent was — that's the whole reason the user is contradicting it. Cost of defending a stale note: lost trust + wrong actions. Cost of checking + obeying: 2 seconds (`mnemosyne_invalidate` + ack). When the user says "invalidate X" or "X is wrong" — do so without defending X. The `mnemosyne_invalidate` operation exists for exactly this reason.

## The "code comment makes a runtime claim" trap

When a comment in source says "we're at http://127.0.0.1:8765/" or "this requires X", the comment records **what the author intended**, not **what the runtime state is right now**. Code comments are documentation of intent; they are not proof of runtime state. The two cheapest verifications: `ls` / `test -f` for paths, `curl -I` / `nc -zv` for services. Cost of trusting a stale comment: hours of debugging the wrong layer. Cost of the verify: 1 second.

**When a code comment makes a runtime claim about state (URL, port, path, service), verify the claim with `ls` or `curl` before trusting the comment. If the comment is stale, fix BOTH the runtime AND the comment.**

## The "user describing their stack is not the same as the stack existing" trap

"I have camofox + searxng + llama-swap + GCP vault" is a CLAIM. Run `docker ps -a`, `netstat -ano | findstr LISTENING`, `test -f`, etc. to verify. The user's mental model of their own environment drifts slower than the actual environment. Across reboots, port re-bindings, container rebuilds, the user remembers "I set this up" but the actual state has moved on.

## The "tool manifest is a list of names, not a list of working tools" trap

If you have a manifest listing MCP tools / endpoints / services, that manifest tells you what COULD work, not what IS working. Each entry needs a live probe:

```bash
# 1. Does the endpoint respond?
hermes mcp test <server-name>

# 2. If it points at a docker container, is the container actually running that image?
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep <server-name>

# 3. If a tool returns results but you've never verified the backend, treat the results as
#    suspect — they're probably coming from a fallback path you didn't intend.
```

**Apply this to every MCP tool, every `mcp__servername__toolname` call, and every claim of "this service exists" before relying on its output.**

## "Newer mtime = canonical" is a backwards heuristic for instance-state dirs

For instance-state directories (`.cache/`, `.local/share/`, runtime config dirs), **mtime is meaningless**. Files get touched on every read in some tools (libcurl, browsers), so a 5-minute-ago mtime means "recently read", not "recently created." For instance-state dirs, use size + presence + last-modified-from-tool-call-pattern, NOT raw mtime.

## The "isn't available" ≠ "hasn't been started" rule

When checking whether something exists, distinguish three states:
- **`verified_absent`** — multi-path scan returned nothing AND service/CLI smoke test fails
- **`installed but not started`** — binary/package/service definition exists but is not currently running
- **`verified present and running`** — binary + service/CLI smoke test both confirm

Saying "X isn't available" when X is actually "X is installed but not started" is the same category of error as "X is down" when X is actually "X is fine, you're looking at the wrong thing." For binaries: check `where <binary>` or `which <binary>` AND try to invoke it. For services: check `systemctl status` / `sc query` / `Get-Service` AND check whether the process is alive.

The right wording for unavailable services:
- ✅ "Docker is installed but the daemon isn't started yet — let me start it."
- ✅ "Playwright isn't started in this session — the server cache exists at `~/.cache/ms-playwright/...`."
- ✅ "The camofox-browser container exists in the Docker image but isn't running yet — should I start it?"
- ❌ "Docker isn't available." (the binary IS available, the daemon just isn't started)
- ❌ "Playwright doesn't exist." (the cached install does exist)
- ❌ "camofox is missing." (the container is missing, but the docker image is cached and can be started)

Wording matters because the user is choosing what to do next. "Not available" suggests the user has to install something; "installed but not started" suggests you can just start it.

## Anti-patterns

DO NOT:
- ❌ "Based on the manual, this should work..." (manual ≠ hardware)
- ❌ "You said you plugged in 3 cables, so 3 must be live" (cables can be wrong type / wrong port)
- ❌ "Most likely explanation is X" (form hypothesis after data, not before)
- ❌ "Try a different cable" without first verifying the cable is the problem
- ❌ "This is protected/bundled, probably can't change it" without checking the actual install
- ❌ Tell the user to "check" something you can check yourself in 5 seconds
- ❌ "I'd need to ask the maintainers" without first reading the local source
- ❌ Form a hypothesis from user description without probing the live state

DO:
- ✅ Run the detection command first
- ✅ State what you FOUND, not what you assume
- ✅ Cite the actual command output that supports your conclusion
- ✅ If 2 sources disagree, say so and explain why
- ✅ If you can't verify, say "I don't know, let me check" — never fabricate
- ✅ Quote manual contradictions when you find them
- ✅ Distinguish "I tried and it failed" from "I assumed it would fail"

## Why this exists

User has corrected this reflex multiple times. The pattern that fails:
1. User describes a real-world system state
2. I form hypothesis from user description + general knowledge
3. I skip the verify step (because the hypothesis feels confident)
4. User has to push back: "did u just go off what i said... without checking"
5. I run the check, find the real answer is different, look incompetent

This skill exists to break step 3. The cost of verifying is always cheaper than the cost of being wrong.