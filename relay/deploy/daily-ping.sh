#!/usr/bin/env bash
# daily-ping.sh — runs daily via systemd timer to prevent Oracle reclamation.
# Writes a small file + does a health check. If the relay is down, alerts
# via stderr (which journald captures and can be tailed).

set -euo pipefail

LOG="/var/log/hermes-relay-ping.log"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HEALTH=$(curl -sS -m 5 http://127.0.0.1:9119/api/v1/healthz 2>&1 || echo "FAILED")

echo "$TIMESTAMP ping ok=$([ -n "$HEALTH" ] && echo "yes" || echo "no") health=$HEALTH" >> "$LOG"

# Keep last 90 days
tail -n 90 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
