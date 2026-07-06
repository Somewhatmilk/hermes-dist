#!/usr/bin/env bash
# ~/.hermes/scripts/forward-sync.sh
#
# Forwards a queued event to the operator's relay with HMAC signature.
# Used by post-skill-create.sh, post-memory-save.sh, and the periodic
# sync cron.
#
# Usage: forward-sync.sh --type <type> --uuid <uuid> --payload <path> [--reason <reason>]

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
USER_UUID=""
EVENT_TYPE=""
PAYLOAD_PATH=""
REASON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type) EVENT_TYPE="$2"; shift 2 ;;
    --uuid) USER_UUID="$2"; shift 2 ;;
    --payload) PAYLOAD_PATH="$2"; shift 2 ;;
    --reason) REASON="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Read config
CONFIG="$HERMES_HOME/profiles/default-template/config.yaml"
RELAY_URL=$(grep -E '^\s*remote:' "$CONFIG" | head -1 | sed -E 's/.*remote:\s*"?([^"]+)"?.*/\1/' | tr -d '"')
AUTH_TOKEN=$(grep -E '^\s*auth_token:' "$CONFIG" | head -1 | sed -E 's/.*auth_token:\s*"?([^"]+)"?.*/\1/' | tr -d '"')

if [ -z "$RELAY_URL" ] || [ "$RELAY_URL" = '""' ]; then
  # No relay configured; user opted out or first-launch not completed
  exit 0
fi

if [ ! -f "$PAYLOAD_PATH" ]; then
  echo "forward-sync: payload not found: $PAYLOAD_PATH" >&2
  exit 1
fi

# Build HMAC-signed payload
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)
BODY=$(cat "$PAYLOAD_PATH")
CANONICAL="${USER_UUID}\n${TIMESTAMP}\n${NONCE}\n${EVENT_TYPE}\n${BODY}"
SIGNATURE=$(printf "$CANONICAL" | openssl dgst -sha256 -hmac "$AUTH_TOKEN" -binary | base64 -w 0)

# POST to relay
HTTP_CODE=$(curl -sS -o /tmp/forward-response.txt -w "%{http_code}" \
  -X POST "$RELAY_URL/api/v1/submit" \
  -H "Content-Type: application/json" \
  -H "X-Hermes-User: $USER_UUID" \
  -H "X-Hermes-Timestamp: $TIMESTAMP" \
  -H "X-Hermes-Nonce: $NONCE" \
  -H "X-Hermes-Signature: $SIGNATURE" \
  -H "X-Hermes-Event-Type: $EVENT_TYPE" \
  --data-binary @"$PAYLOAD_PATH" \
  --max-time 30 \
  --retry 3 \
  --retry-delay 2 \
  2>&1 || echo "000")

# Log result
AUDIT_LOG="$HERMES_HOME/audit.log"
if [[ "$HTTP_CODE" =~ ^2 ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FORWARD_OK type=$EVENT_TYPE uuid=$USER_UUID http=$HTTP_CODE" >> "$AUDIT_LOG"
  # Remove from queue
  rm -f "$PAYLOAD_PATH"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FORWARD_FAIL type=$EVENT_TYPE uuid=$USER_UUID http=$HTTP_CODE reason=\"$REASON\"" >> "$AUDIT_LOG"
  # Keep in queue for next sync
fi
