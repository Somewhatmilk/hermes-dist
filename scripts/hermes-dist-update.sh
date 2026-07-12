#!/usr/bin/env bash
# hermes-dist-update.sh — Daily update check + toast.
#
# Runs from systemd user timer (Linux) or launchd plist (macOS). NOT meant to
# be invoked directly by users.
#
# Behavior (v0.4.0 design):
#   1. git pull --ff-only the hermes-dist repo (silent, fast-forward only)
#   2. Query https://api.github.com/repos/<owner>/hermes-dist/releases/latest
#   3. Compare tag_name against the locally-pinned version
#   4. If newer: show a toast + leave a notice file. NO auto-apply.
#
# To apply the update, the user runs:
#   hermes update-dist
# (which is in their hermes-agent install and shows the diff + applies)
#
# Environment / arguments:
#   HERMES_DIST_REPO       git URL (default: https://github.com/Somewhatmilk/hermes-dist.git)
#   HERMES_DIST_DIR        local clone dir (default: $HOME/hermes-dist)
#   HERMES_PIN_FILE       file with the locally-pinned tag (default: $HERMES_DIST_DIR/.hermes-dist-version)
#   QUIET=1                suppress toast (for testing)
#
# OS-specific toast:
#   Linux:  notify-send (libnotify, comes with most desktops)
#   macOS:  osascript -e 'display notification ... with title ...'
#   Other:  printf to stderr (silent fallback)

set -euo pipefail

HERMES_DIST_REPO="${HERMES_DIST_REPO:-https://github.com/Somewhatmilk/hermes-dist.git}"
HERMES_DIST_DIR="${HERMES_DIST_DIR:-$HOME/hermes-dist}"
HERMES_PIN_FILE="${HERMES_PIN_FILE:-$HERMES_DIST_DIR/.hermes-dist-version}"

# 1. git pull --ff-only (silent fast-forward)
if [ -d "$HERMES_DIST_DIR/.git" ]; then
    (cd "$HERMES_DIST_DIR" && git pull --ff-only 2>&1 | head -5 || true)
fi

# 2. Query GitHub releases API for the latest tag (no auth needed)
if ! command -v curl >/dev/null 2>&1; then
    echo "✗ hermes-dist-update.sh: curl not found" >&2
    exit 1
fi

LATEST_JSON="$(curl -fsSL --max-time 10 \
    "${HERMES_DIST_REPO%.git}/releases/latest" 2>/dev/null || true)"

if [ -z "$LATEST_JSON" ]; then
    # Network down or rate-limited — silent exit, will retry tomorrow
    exit 0
fi

# Extract tag_name from the JSON. Use grep+sed for portability (no jq required).
LATEST_TAG="$(printf '%s' "$LATEST_JSON" | grep -oE '"tag_name"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 | sed -E 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"

if [ -z "$LATEST_TAG" ]; then
    # No tag_name found (e.g. repo has no releases yet)
    exit 0
fi

# 3. Compare against locally-pinned tag
PINNED=""
if [ -f "$HERMES_PIN_FILE" ]; then
    PINNED="$(cat "$HERMES_PIN_FILE" 2>/dev/null | tr -d '[:space:]')"
fi

# If we have no pin yet, write the current tag as the pin and exit
if [ -z "$PINNED" ]; then
    echo "$LATEST_TAG" > "$HERMES_PIN_FILE"
    exit 0
fi

# If pinned tag matches latest, nothing to do
if [ "$PINNED" = "$LATEST_TAG" ]; then
    exit 0
fi

# 4. New version available — show toast + write notice
TITLE="hermes-dist update available"
MSG="hermes-dist $LATEST_TAG available (current: $PINNED). Run 'hermes update-dist' to review and apply."

# Write notice file for hermes-update-dist to read
NOTICE_FILE="$HERMES_DIST_DIR/.hermes-dist-pending"
cat > "$NOTICE_FILE" <<EOF
{
  "detected_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "from_tag": "$PINNED",
  "to_tag": "$LATEST_TAG",
  "status": "pending_user_approval"
}
EOF

if [ "${QUIET:-0}" = "1" ]; then
    exit 0
fi

# OS-specific toast
case "${OSTYPE:-unknown}" in
    linux*|linux-gnu*)
        # notify-send (libnotify-bin on Debian/Ubuntu, libnotify on Fedora/Arch)
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -u normal -t 0 "$TITLE" "$MSG" 2>/dev/null || true
        fi
        # Fallback: log to journal + stderr
        if [ -n "${JOURNAL_STREAM:-}" ]; then
            echo "$TITLE: $MSG" | systemd-cat -t hermes-dist-update 2>/dev/null || true
        fi
        echo "$TITLE: $MSG" >&2
        ;;
    darwin*)
        # macOS Notification Center via osascript
        osascript -e "display notification \"$MSG\" with title \"$TITLE\"" 2>/dev/null || true
        echo "$TITLE: $MSG" >&2
        ;;
    *)
        # Unknown OS — silent fallback
        echo "$TITLE: $MSG" >&2
        ;;
esac

# Write a user-readable summary to stderr for journalctl / log show
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) hermes-dist-update: $PINNED -> $LATEST_TAG (pending user approval)" >&2

exit 0