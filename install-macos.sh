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

# ─── 7. launchd plist: daily update check at 09:00 ─────────────────────────
# Pattern from skill cross-platform-bash-scripting §4d (darwin branch).
# Plists live under ~/Library/LaunchAgents/ and load via `launchctl load -w`.
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
LOGS_DIR="$HERMES_HOME/logs"
mkdir -p "$LOGS_DIR"

UPDATE_LABEL="com.user.hermes-dist-update"
UPDATE_PLIST="$LAUNCH_AGENTS_DIR/${UPDATE_LABEL}.plist"
HEARTBEAT_LABEL="com.user.hermes-dist-heartbeat"
HEARTBEAT_PLIST="$LAUNCH_AGENTS_DIR/${HEARTBEAT_LABEL}.plist"

# Helper to unregister a stale plist before re-registering (mac update case).
unregister_plist() {
    local label="$1" plist="$2"
    if [ -f "$plist" ]; then
        launchctl unload "$plist" 2>/dev/null || true
    fi
}

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
        <string>-c</string>
        <string>cd '${DIST_DIR}' &amp;&amp; git pull --ff-only 2&gt;&amp;1 | head -20</string>
    </array>
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

write_heartbeat_plist() {
    cat > "$HEARTBEAT_PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${HEARTBEAT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${HERMES_BIN}</string>
        <string>heartbeat</string>
        <string>--relay</string>
        <string>${HERMES_RELAY_URL}</string>
    </array>
    <key>StartInterval</key><integer>60</integer>
    <key>StandardOutPath</key><string>${LOGS_DIR}/heartbeat.log</string>
    <key>StandardErrorPath</key><string>${LOGS_DIR}/heartbeat.err</string>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
PLIST_EOF
}

if [ "${SKIP_SCHEDULER:-0}" = "1" ]; then
    echo
    echo "  ⚠ SKIP_SCHEDULER=1 — not registering launchd plist"
else
    unregister_plist "$UPDATE_LABEL" "$UPDATE_PLIST"
    write_update_plist
    # Validate the plist before loading — launchctl's plist parse error is unhelpful.
    if plutil -lint "$UPDATE_PLIST" >/dev/null 2>&1; then
        launchctl load -w "$UPDATE_PLIST"
        echo "  ✓ Registered launchd plist: $UPDATE_PLIST"
    else
        echo "  ✗ Failed to validate $UPDATE_PLIST (plist syntax error)" >&2
        plutil -lint "$UPDATE_PLIST" >&2 || true
    fi
fi

# ─── 8. launchd heartbeat (60s poll) ───────────────────────────────────────
if [ "${SKIP_HEARTBEAT:-0}" = "1" ]; then
    echo "  ⚠ SKIP_HEARTBEAT=1 — not starting heartbeat"
else
    unregister_plist "$HEARTBEAT_LABEL" "$HEARTBEAT_PLIST"
    write_heartbeat_plist
    if plutil -lint "$HEARTBEAT_PLIST" >/dev/null 2>&1; then
        launchctl load -w "$HEARTBEAT_PLIST"
        echo "  ✓ Heartbeat started (60s poll, $HEARTBEAT_LABEL)"
    else
        echo "  ✗ Failed to validate $HEARTBEAT_PLIST (plist syntax error)" >&2
        plutil -lint "$HEARTBEAT_PLIST" >&2 || true
    fi
fi

# ─── 9. Final summary ──────────────────────────────────────────────────────
echo
echo "=== Installation Complete (macOS) ==="
echo "  HERMES_HOME:   $HERMES_HOME"
echo "  WORKING_DIR:   $WORKING_DIR"
echo "  Dist bundle:   $DIST_DIR"
echo "  Relay URL:     $HERMES_RELAY_URL"
echo "  Scheduler:     launchd plist ($UPDATE_PLIST)"
echo "  Heartbeat:     launchd plist ($HEARTBEAT_PLIST, 60s StartInterval)"
echo
echo "Launch with: hermes chat"
echo "Logs:        $LOGS_DIR"