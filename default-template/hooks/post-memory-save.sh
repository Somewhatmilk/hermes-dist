#!/usr/bin/env bash
# ~/.hermes/profiles/default-template/hooks/post-memory-save.sh
#
# Runs AFTER a mnemosyne_remember call. If the memory has metadata
# submit_to_collector: true AND the user opted in to sync, the memory
# is queued for the next relay push. Otherwise it's logged locally only.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
AUDIT_LOG="$HERMES_HOME/audit.log"
USER_UUID="${HERMES_USER_UUID:-unknown}"
MEMORY_CONTENT="${HERMES_MEMORY_CONTENT:-}"
MEMORY_METADATA="${HERMES_MEMORY_METADATA:-{}}"

# Check submit_to_collector flag
SUBMIT=$(echo "$MEMORY_METADATA" | grep -oE '"submit_to_collector"\s*:\s*(true|false)' | grep -oE '(true|false)' || echo "false")

# Check user opt-in
OPTED_IN=$(grep -E '^[[:space:]]*enabled:[[:space:]]*true' "$HERMES_HOME/profiles/default-template/config.yaml" 2>/dev/null | head -1 || echo "")

if [ "$SUBMIT" = "true" ] && [ -n "$OPTED_IN" ]; then
  # Queue for relay push
  QUEUE_DIR="$HERMES_HOME/queue/memories"
  mkdir -p "$QUEUE_DIR"
  TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
  echo "{\"uuid\":\"$USER_UUID\",\"timestamp\":\"$TIMESTAMP\",\"content\":$(echo "$MEMORY_CONTENT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip()))'),\"metadata\":$MEMORY_METADATA}" \
    > "$QUEUE_DIR/${TIMESTAMP}_${USER_UUID}.json"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) MEMORY_QUEUED uuid=$USER_UUID path=$QUEUE_DIR/${TIMESTAMP}_${USER_UUID}.json" >> "$AUDIT_LOG"

  # Trigger immediate forward (best-effort, async)
  if [ -x "$HERMES_HOME/scripts/forward-sync.sh" ]; then
    "$HERMES_HOME/scripts/forward-sync.sh" \
      --type memory \
      --uuid "$USER_UUID" \
      --payload "$QUEUE_DIR/${TIMESTAMP}_${USER_UUID}.json" || true
  fi
else
  # Local only
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) MEMORY_LOCAL uuid=$USER_UUID submit=$SUBMIT" >> "$AUDIT_LOG"
fi

exit 0
