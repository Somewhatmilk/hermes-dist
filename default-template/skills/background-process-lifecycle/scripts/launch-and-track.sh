#!/usr/bin/env bash
# ~/.hermes/scripts/launch-and-track.sh
# Canonical launch-and-track pattern for long-running background processes.
# Usage:
#   launch-and-track.sh <purpose> <command...>
# Example:
#   launch-and-track.sh gateway "hermes gateway start"
# Output: prints PID + log path + persists to ~/.hermes/state/background-sessions.tsv
# Use --list to dump the tracking file.

set -euo pipefail

PURPOSE="${1:?usage: launch-and-track.sh <purpose> <command...>}"

if [[ "$PURPOSE" == "--list" ]]; then
  STATE_DIR="$HOME/.hermes/state"
  TSV="$STATE_DIR/background-sessions.tsv"
  if [[ -f "$TSV" ]]; then
    echo "=== tracked background sessions ==="
    cat "$TSV"
  else
    echo "(no tracking file yet)"
  fi
  exit 0
fi

shift

STATE_DIR="$HOME/.hermes/state"
TSV="$STATE_DIR/background-sessions.tsv"
mkdir -p "$STATE_DIR"
[ -f "$TSV" ] || printf 'started\tpurpose\tcommand\tsession_id\tpid\n' > "$TSV"

LOG="$STATE_DIR/bg-${PURPOSE}-$(date +%Y%m%d-%H%M%S).log"

# Use `start //B` on Windows (MSYS) which detaches via CreateProcess; on *nix use nohup+disown.
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
  MSYS_NO_PATHCONV=1 start //B bash -c "$* > '$LOG' 2>&1" &
  PID=$!
  SESSION_ID="(shell-detach, pid=$PID)"
else
  nohup bash -c "$*" > "$LOG" 2>&1 &
  PID=$!
  disown
  SESSION_ID="(shell-detach, pid=$PID)"
fi

printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Iseconds)" "$PURPOSE" "$*" "$SESSION_ID" "$PID" >> "$TSV"

echo "background launch:"
echo "    purpose:  $PURPOSE"
echo "    pid:      $PID"
echo "    log:      $LOG"
echo "    tracking: $TSV"
echo
echo "to monitor:  tail -f '$LOG'"
echo "to stop:     kill $PID  (or taskkill /F /PID $PID on Windows)"
echo "to list:     $0 --list"
