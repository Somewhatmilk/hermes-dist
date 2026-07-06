#!/usr/bin/env bash
# .onboard.sh — first-launch for Mac/Linux users.
# Same logic as install-windows.ps1 but bash-native.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DIST_REPO="${HERMES_DIST_REPO:-${1:-}}"
RELAY_URL="${HERMES_RELAY_URL:-https://relay.local}"

# Verify prerequisites
command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "git not found"; exit 1; }

# Install Hermes if missing
if ! command -v hermes >/dev/null 2>&1; then
    echo "Installing Hermes Agent..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi

# Clone dist repo
DIST_DIR="$HOME/hermes-dist"
if [ ! -d "$DIST_DIR" ] && [ -n "$DIST_REPO" ]; then
    git clone "$DIST_REPO" "$DIST_DIR"
fi

# Run the actual onboarding
cd "$DIST_DIR"
HERMES_HOME="$HERMES_HOME" HERMES_DIST_REPO="$DIST_REPO" HERMES_RELAY_URL="$RELAY_URL" \
    bash .onboard.sh
