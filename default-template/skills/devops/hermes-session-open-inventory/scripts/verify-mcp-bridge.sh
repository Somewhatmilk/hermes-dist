#!/usr/bin/env bash
# verify-mcp-bridge.sh — Distinguish service-down / MCP-bridge / GPG-prompt
#
# Reusable probe for the MCP bridge failure pattern where the agent's
# tool manifest has no mcp__<server>__* entries even though the
# service is up. Three states, three different fixes.
#
# Usage:  verify-mcp-bridge.sh <service-name> <port>
#   e.g.  verify-mcp-bridge.sh tinysearch 8000
#
# Idempotent: read-only, safe to re-run.
# Cost: <30s.
# Returns: never errors out; always reports the discriminating state.
#          Exit code 0 on success, 1 only on internal script bug.
set -euo pipefail

SERVICE="${1:-tinysearch}"
PORT="${2:-8000}"

echo "=== MCP Bridge Diagnostic — $(date -Iseconds) ==="
echo "Target: $SERVICE on 127.0.0.1:$PORT"
echo

# A. Service alive?
echo "[A] Service alive?"
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null | grep -i "$SERVICE" >/dev/null; then
    echo "  OK docker container present:"
    docker ps --format '    {{.Names}}	{{.Status}}' 2>/dev/null | grep -i "$SERVICE"
  else
    echo "  FAIL no docker container matching '$SERVICE'"
    echo "  Fix: docker compose up -d $SERVICE"
    exit 0
  fi
else
  echo "  (no docker — falling back to netstat)"
  if netstat -ano 2>/dev/null | grep ":$PORT " | grep LISTENING >/dev/null; then
    netstat -ano | grep ":$PORT " | grep LISTENING | head -3
  else
    echo "  FAIL nothing on :$PORT"
    exit 0
  fi
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
