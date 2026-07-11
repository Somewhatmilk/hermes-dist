---
name: mcp-bridge-vs-gpg-confusion-2026-07-07
description: MCP transport / gateway / model-manifest bridge failure, distinguished from the GPG pass-vault boot-time prompt. Concrete 2026-07-07 transcript and reusable probe script.
type: incident-transcript
created: 2026-07-07
applies-to: hermes-session-open-inventory, hermes-llm-preflight
---

# MCP Bridge vs GPG Confusion — 2026-07-07

## The user-reported symptom

"MCP might not be reachable due to GPG" — phrasing that conflates TWO independent problems:

1. **GPG passphrase prompt at boot** — the pass-vault secret-load at Hermes
   startup prompts for a passphrase because the MSYS gpg-agent dies with
   the bash session. The prompt is a *boot-time* issue with secret unlocking.
2. **MCP tools absent from the model manifest** — `mcp__tinysearch__*`,
   `mcp__searxng__*` etc. don't appear in the agent's tool surface even
   though the containers are running.

The user correctly noticed both symptoms. The agent's failure mode was
to treat the GPG prompt as the *cause* of the MCP absence, and start
reasoning from "fix GPG → MCP will come back." That reasoning was wrong:
the GPG prompt is independent of MCP reachability. Fixing GPG would not
have made the MCP tools reappear.

## The 3-state model (from the parent skill's pitfall #16)

| State | Probe | Fix |
|---|---|---|
| **Service down** | `docker ps` empty / port not listening | `docker compose up -d` / start service |
| **MCP transport broken** (most common) | `curl POST /mcp` returns HTTP 200 + `mcp-session-id`; `mcp__<server>__*` still absent from manifest | `hermes gateway restart` + `/new` |
| **GPG prompt unrelated** | any time | fix GPG separately; does not affect MCP |

## Reusable probe — `verify-mcp-bridge.sh`

Lives at `~/.hermes/scripts/verify-mcp-bridge.sh`. Idempotent, no
side effects, runs in <30s. Rerunning is safe; the script is read-only.

```bash
#!/usr/bin/env bash
# verify-mcp-bridge.sh — Distinguish service-down / MCP-bridge / GPG-prompt
# Usage: verify-mcp-bridge.sh <service-name> <port>
#   e.g.  verify-mcp-bridge.sh tinysearch 8000
#         verify-mcp-bridge.sh searxng     8888
set -euo pipefail

SERVICE="${1:-tinysearch}"
PORT="${2:-8000}"

echo "=== MCP Bridge Diagnostic — $(date -Iseconds) ==="
echo "Target: $SERVICE on 127.0.0.1:$PORT"
echo

# A. Service alive?
echo "[A] Service alive?"
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}\t{{.Status}}' | grep -i "$SERVICE" >/dev/null; then
    echo "  OK docker container present:"
    docker ps --format '    {{.Names}}	{{.Status}}' | grep -i "$SERVICE"
  else
    echo "  FAIL no docker container matching '$SERVICE'"
    echo "  Fix: docker compose up -d $SERVICE"
    exit 0
  fi
else
  echo "  (no docker — falling back to netstat)"
  netstat -ano | grep ":$PORT " | grep LISTENING | head -3 || echo "  FAIL nothing on :$PORT"
fi
echo

# B. MCP transport alive?
echo "[B] MCP transport alive? (POST /mcp initialize)"
RESP=$(curl -s -m 5 -i -X POST "http://127.0.0.1:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify-mcp-bridge","version":"1.0.0"}}}' \
  2>&1) || true
echo "$RESP" | head -8
echo
if echo "$RESP" | grep -qi "mcp-session-id"; then
  echo "  OK MCP transport responding with session id"
else
  echo "  FAIL MCP transport NOT responding correctly"
  echo "  Fix: check container logs (docker logs <container>)"
  exit 0
fi
echo

# C. Decision
echo "[C] Decision"
echo "  If A and B both pass but mcp__${SERVICE}__* is still absent from the agent's"
echo "  tool surface -> MCP-bridge state, NOT a GPG or container problem."
echo "  Fix:"
echo "    hermes gateway restart"
echo "    # in TUI: /new   (forces manifest rebuild)"
echo
echo "  GPG-passphrase prompt at boot is a SEPARATE issue:"
echo "    gpgconf --kill gpg-agent   # restart gpg-agent"
echo "    # OR: pin the agent to a long-running tty so gpg-agent persists"
echo "    # OR: switch to a non-GPG secret store (pass-cli, age, etc.)"
echo
echo "=== END ==="
```

Usage in a TUI session:

```bash
chmod +x ~/.hermes/scripts/verify-mcp-bridge.sh
~/.hermes/scripts/verify-mcp-bridge.sh tinysearch 8000
~/.hermes/scripts/verify-mcp-bridge.sh searxng 8888
```

## Concrete transcript (this incident)

```
$ docker ps --format '{{.Names}}\t{{.Status}}' | grep -i tiny
tinysearch-tinysearch-1   Up 14 hours (healthy)

$ curl -s -m 5 -i -X POST http://127.0.0.1:8000/mcp \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'
HTTP/1.1 200 OK
content-type: text/event-stream
mcp-session-id: 9c3e6f8a-...
# transport responding, session id issued

# But agent's tool surface has zero mcp__tinysearch__* entries.
# That's the bridge problem.

$ hermes gateway restart
$ # in TUI: /new

# After restart: mcp__tinysearch__search now in the tool manifest.
```

## What the user said vs what was actually wrong

| User statement | Actual state | Right action |
|---|---|---|
| "MCP not reachable due to GPG" | GPG and MCP were both imperfect, but **independently**. GPG was a real prompt; MCP was a bridge issue, not a GPG issue. | Run the 3-state probe; fix the bridge with `hermes gateway restart`. Don't touch GPG. |
| "tinysearch doesn't work" | Container up, transport up, gateway not bridging. | Restart gateway; verify manifest. |

## Three lessons to keep

1. **Co-occurring symptoms are not causally related.** Two things broken at
   once is common; the agent must still diagnose them separately.
2. **"User said X is broken" + "user said Y might cause X" is not the same
   as "X is caused by Y."** Run the discriminating probe.
3. **The "third state" is the most common one.** Service up + transport
   up + manifest empty → the bridge. Don't start reasoning from "the
   service is down" when both A and B pass.
