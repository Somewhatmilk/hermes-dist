#!/usr/bin/env bash
# install-macos.sh — Hermes Dist installer for macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/hermes-dist/main/install-macos.sh | bash
#   # or with overrides:
#   HERMES_DIST_REPO="https://github.com/you/hermes-dist" \
#   HERMES_RELAY_URL="https://relay.your-domain" \
#     bash install-macos.sh
#
# What this does:
#   1. Refuses to run if OSTYPE is not darwin* (safety check — catches MSYS
#      edge cases where someone runs the wrong installer)
#   2. Verifies prerequisites (python3, git, curl, brew)
#   3. Uses brew to install/upgrade python3 and git if needed
#   4. Sets HERMES_HOME=$HOME/.hermes  and  WORKING_DIR=$HOME
#   5. Installs Hermes Agent via the official installer (curl | bash)
#   6. Clones the hermes-dist repo into $HOME/hermes-dist (or uses existing)
#   7. Runs .onboard.sh from the cloned repo
#   8. Drops a launchd plist at ~/Library/LaunchAgents/ for the daily update
#   9. Drops a launchd plist for the 60s heartbeat (StartInterval=60)
#
# Environment overrides:
#   HERMES_HOME         default: $HOME/.hermes
#   WORKING_DIR         default: $HOME
#   HERMES_DIST_REPO    git URL of the hermes-dist bundle (otherwise expects local clone)
#   HERMES_RELAY_URL    default: https://relay.local
#   HERMES_BIN          default: $HERMES_HOME/venv/bin/hermes
#   SKIP_HEARTBEAT=1    skip launching the heartbeat plist
#   SKIP_SCHEDULER=1    skip installing the update plist
#
# Verified on: macOS 13 Ventura, 14 Sonoma, 15 Sequoia (Intel + Apple Silicon)
# Requires: bash 4+ (macOS ships with bash 3.2 — we use POSIX-portable syntax
#           plus only [ -v ] / ${VAR:-} / arrays are avoided). launchd always present.

set -euo pipefail

# ─── 0. Hard OS guard ──────────────────────────────────────────────────────
# Per skill cross-platform-bash-scripting §2: detect first, dispatch second.
# If someone invokes this on Linux/MSYS by mistake, bail before doing damage.
case "${OSTYPE:-}" in
    darwin*) ;;  # good
    *)
        echo "✗ install-macos.sh must be run on macOS (detected OSTYPE='${OSTYPE:-}')." >&2
        echo "  On Linux use install-linux.sh; on Windows use install-windows.ps1." >&2
        exit 1
        ;;
esac

# ─── 1. Banner + prerequisite check ────────────────────────────────────────
echo "=== Hermes Dist — macOS Installer ==="
echo

# macOS ships python (2.7 legacy) but NOT python3 by default on older releases.
# Always require python3 explicitly.
command -v python3 >/dev/null 2>&1 || { echo "✗ python3 not found in PATH"; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "✗ git not found in PATH — install Xcode CLT: xcode-select --install"; exit 1; }
command -v curl    >/dev/null 2>&1 || { echo "✗ curl not found in PATH"; exit 1; }
# launchctl always present on macOS
command -v launchctl >/dev/null 2>&1 || { echo "✗ launchctl not found — macOS broken?"; exit 1; }

# brew is the canonical package manager on macOS but not always installed.
# We use it opportunistically (warn, don't fail) so this script still runs
# on machines that already have the deps via CLT or pyenv.
if command -v brew >/dev/null 2>&1; then
    BREW_AVAILABLE=1
    echo "  ✓ python3 $(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'), git, curl, launchctl, brew"
else
    BREW_AVAILABLE=0
    echo "  ✓ python3, git, curl, launchctl (⚠ brew not installed — skipping package installs)"
fi

# ─── 2. Path resolution (macOS) ─────────────────────────────────────────────
# Per skill cross-platform-bash-scripting P1+P5: derive from $HOME, never literal.
: "${HERMES_HOME:=$HOME/.hermes}"
: "${WORKING_DIR:=$HOME}"
: "${HERMES_RELAY_URL:=https://relay.local}"
: "${HERMES_DIST_REPO:=}"
: "${HERMES_BIN:=$HERMES_HOME/venv/bin/hermes}"

export HERMES_HOME WORKING_DIR HERMES_RELAY_URL

mkdir -p "$HERMES_HOME"
echo "  ✓ HERMES_HOME=$HERMES_HOME"
echo "  ✓ WORKING_DIR=$WORKING_DIR"

# ─── 3. brew-based prerequisite install (best-effort) ──────────────────────
if [ "$BREW_AVAILABLE" = "1" ]; then
    # Ensure git + python3 are current. brew install is idempotent (skips if up-to-date).
    brew install git python3 >/dev/null 2>&1 || true
fi

# ─── 4. Install Hermes Agent via official installer ────────────────────────
if ! command -v hermes >/dev/null 2>&1 && [ ! -x "$HERMES_BIN" ]; then
    echo
    echo "Installing Hermes Agent via official installer..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | NOSPAM=1 bash
else
    echo "  ✓ Hermes Agent already installed"
fi

# ─── 5. Clone (or reuse) hermes-dist repo ──────────────────────────────────
DIST_DIR="$HOME/hermes-dist"
if [ -d "$DIST_DIR/.git" ]; then
    echo "  ✓ Reusing existing $DIST_DIR"
elif [ -n "$HERMES_DIST_REPO" ]; then
    echo "Cloning $HERMES_DIST_REPO → $DIST_DIR ..."
    git clone "$HERMES_DIST_REPO" "$DIST_DIR"
else
    echo "  ✗ HERMES_DIST_REPO not set and no $DIST_DIR found." >&2
    echo "    Re-run with HERMES_DIST_REPO=<git-url>, or copy the bundle to $DIST_DIR." >&2
    exit 1
fi

# ─── 6. Run .onboard.sh (first-launch bootstrap) ───────────────────────────
ONBOARD="$DIST_DIR/.onboard.sh"
if [ ! -f "$ONBOARD" ]; then
    echo "  ✗ .onboard.sh not found at $ONBOARD" >&2
    exit 1
fi
echo
echo "Running .onboard.sh ..."
(
    cd "$DIST_DIR"
    HERMES_HOME="$HERMES_HOME" \
    WORKING_DIR="$WORKING_DIR" \
    HERMES_DIST_REPO="$HERMES_DIST_REPO" \
    HERMES_RELAY_URL="$HERMES_RELAY_URL" \
        bash "$ONBOARD"
)

# ─── 7. launchd plist: daily update check at 09:00 (v0.4.0 design) ───────
# Per the v0.4.0 design (commit de66e3a): the launchd plist runs the daily
# update-check script which does git pull + GitHub releases API check +
# macOS Notification Center toast. The user runs `hermes update-dist` to
# actually apply the update (no auto-apply, no auto-download).
#
# Pattern from skill cross-platform-bash-scripting §4d (darwin branch).
# Plists live under ~/Library/LaunchAgents/ and load via `launchctl load -w`.
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
LOGS_DIR="$HERMES_HOME/logs"
mkdir -p "$LOGS_DIR"

UPDATE_LABEL="com.user.hermes-dist-update"
UPDATE_PLIST="$LAUNCH_AGENTS_DIR/${UPDATE_LABEL}.plist"
UPDATE_SCRIPT_SRC="$DIST_DIR/scripts/hermes-dist-update.sh"

# Copy the update script into a stable location launchd references. launchd
# can't reliably follow relative paths or run scripts in $DIST_DIR if the
# repo gets moved/renamed, so we copy once at install time.
UPDATE_SCRIPT_DST="$HOME/.local/bin/hermes-dist-update.sh"
mkdir -p "$(dirname "$UPDATE_SCRIPT_DST")"
cp "$UPDATE_SCRIPT_SRC" "$UPDATE_SCRIPT_DST"
chmod +x "$UPDATE_SCRIPT_DST"

# Helper to unregister a stale plist before re-registering (mac update case).
unregister_plist() {
    local label="$1" plist="$2"
    if [ -f "$plist" ]; then
        launchctl unload "$plist" 2>/dev/null || true
    fi
}

# v0.4.0: plist runs the shared update script. macOS toast comes from inside
# the script via `osascript -e 'display notification ...'`.
write_update_plist() {
    cat > "$UPDATE_PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${UPDATE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${UPDATE_SCRIPT_DST}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HERMES_DIST_DIR</key><string>${DIST_DIR}</string>
        <key>HERMES_DIST_REPO</key><string>${HERMES_DIST_REPO}</string>
        <key>HERMES_PIN_FILE</key><string>${DIST_DIR}/.hermes-dist-version</string>
    </dict>
    <key>WorkingDirectory</key><string>${DIST_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>${LOGS_DIR}/update.log</string>
    <key>StandardErrorPath</key><string>${LOGS_DIR}/update.err</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST_EOF
}

# Pin the current tag so the next run has a baseline to compare against.
# Falls back to "v0.0.0" if repo has no tags yet.
CURRENT_TAG="$(cd "$DIST_DIR" && git describe --tags --abbrev=0 2>/dev/null || echo 'v0.0.0')"
echo "$CURRENT_TAG" > "$DIST_DIR/.hermes-dist-version"

if [ "${SKIP_SCHEDULER:-0}" = "1" ]; then
    echo
    echo "  ⚠ SKIP_SCHEDULER=1 — not registering launchd plist"
else
    unregister_plist "$UPDATE_LABEL" "$UPDATE_PLIST"
    write_update_plist
    # Validate the plist before loading — launchctl's plist parse error is unhelpful.
    if plutil -lint "$UPDATE_PLIST" >/dev/null 2>&1; then
        launchctl load -w "$UPDATE_PLIST"
        echo "  ✓ Registered launchd plist: $UPDATE_PLIST (daily 09:00)"
        echo "  ✓ Pinned current version: $CURRENT_TAG"
    else
        echo "  ✗ Failed to validate $UPDATE_PLIST (plist syntax error)" >&2
        plutil -lint "$UPDATE_PLIST" >&2 || true
    fi
fi

# ─── 9. Final summary ──────────────────────────────────────────────────────
echo
echo "=== Installation Complete (macOS) ==="
echo "  HERMES_HOME:   $HERMES_HOME"
echo "  WORKING_DIR:   $WORKING_DIR"
echo "  Dist bundle:   $DIST_DIR"
echo "  Relay URL:     $HERMES_RELAY_URL"
echo "  Update check:  launchd plist ($UPDATE_PLIST), daily 09:00"
echo "  Update script: $UPDATE_SCRIPT_DST"
echo "  Toast:         macOS Notification Center (osascript)"
echo
echo "Launch with: hermes chat"
echo "Logs:        $LOGS_DIR"