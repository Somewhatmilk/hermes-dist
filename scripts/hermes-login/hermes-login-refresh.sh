#!/usr/bin/env bash
# hermes-login-refresh.sh - runs as Task Scheduler / systemd user timer / launchd
# Calls hermes login refresh with stored state.
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
OPERATOR_HOST=$(cat "$HERMES_HOME/.operator-host" 2>/dev/null || echo "")
if [ -z "$OPERATOR_HOST" ]; then
    echo "[login-refresh] no operator host configured at $HERMES_HOME/.operator-host"
    exit 0
fi
python "$HERMES_HOME/bin/hermes-login.py" refresh --operator "$OPERATOR_HOST"