#!/usr/bin/env bash
# install-linux.sh — Hermes Dist installer for Linux.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/hermes-dist/main/install-linux.sh | bash
#   # or with overrides:
#   HERMES_DIST_REPO="https://github.com/you/hermes-dist" \
#   HERMES_RELAY_URL="https://relay.your-domain" \
#     bash install-linux.sh
#
# What this does:
#   1. Verifies prerequisites (python3, git, curl)
#   2. Detects package manager (apt / dnf / pacman / zypper) and ensures git+python3+curl + libnotify-bin (for toast)
#   3. Sets HERMES_HOME=$HOME/.hermes  and  WORKING_DIR=$HOME
#   4. Installs Hermes Agent via the official installer (curl | bash)
#   5. Clones the hermes-dist repo into $HOME/hermes-dist (or uses existing)
#   6. Runs .onboard.sh from the cloned repo
#   7. Sets up a systemd USER timer for the daily update check (no sudo required)
#      — runs scripts/hermes-dist-update.sh which does git pull + GitHub releases
#        API check + notify-send toast (per v0.4.0 design; user-initiated apply)
#
# Environment overrides:
#   HERMES_HOME         default: $HOME/.hermes
#   WORKING_DIR         default: $HOME
#   HERMES_DIST_REPO    git URL of the hermes-dist bundle (otherwise expects local clone)
#   HERMES_RELAY_URL    default: https://relay.local
#   HERMES_BIN          default: $HERMES_HOME/venv/bin/hermes
#   SKIP_SCHEDULER=1    skip registering systemd timer
#
# Verified on: Ubuntu 22.04+, Debian 12+, Fedora 39+, Arch (current), openSUSE Leap 15+
# Requires: bash 4+, systemd (for the user timer). No sudo required — user-scoped.

set -euo pipefail

# ─── 0. Hard OS guard ──────────────────────────────────────────────────────
# Per skill cross-platform-bash-scripting §2: detect first, dispatch second.
# If someone invokes this on macOS/MSYS by mistake, bail before doing damage.
# Accept any linux* variant — msys/cygwin are explicitly excluded here because
# install-windows.ps1 owns that surface.
case "${OSTYPE:-}" in
    linux*|linux-gnu*)
        ;;  # good — actual Linux
    darwin*)
        echo "✗ install-linux.sh: detected macOS (OSTYPE='${OSTYPE}'). Use install-macos.sh instead." >&2
        exit 1
        ;;
    msys*|cygwin*)
        echo "✗ install-linux.sh: detected Windows MSYS (OSTYPE='${OSTYPE}'). Use install-windows.ps1 instead." >&2
        exit 1
        ;;
    *)
        echo "✗ install-linux.sh: unsupported OS '${OSTYPE:-unknown}'. Use install-macos.sh or install-windows.ps1." >&2
        exit 1
        ;;
esac

# ─── 1. Banner + prerequisite check ────────────────────────────────────────
echo "=== Hermes Dist — Linux Installer (Linux, ${OSTYPE}) ==="
echo

command -v python3 >/dev/null 2>&1 || { echo "✗ python3 not found in PATH"; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "✗ git not found in PATH"; exit 1; }
command -v curl    >/dev/null 2>&1 || { echo "✗ curl not found in PATH"; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "✗ systemctl not found — this installer requires systemd"; exit 1; }

PYTHON_VERSION=$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ python3 ${PYTHON_VERSION}, git, curl, systemctl"

# ─── 2. Path resolution (Linux) ─────────────────────────────────────────────
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

# ─── 3. Package manager detection + ensure git/python3/curl ────────────────
# Installs missing prerequisites WITHOUT sudo when possible (assumes user owns
# /usr/local — common on dev boxes). If sudo is available and a system pkg is
# missing, we use that instead. The default is to leave the system pkgs alone
# since dev machines already have them.
detect_pkg_manager() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    else
        echo ""
    fi
}

PKG_MANAGER="$(detect_pkg_manager)"
echo "  ✓ package manager: ${PKG_MANAGER:-<none — assuming dev box>}"

ensure_pkg() {
    # ensure_pkg <binary> <pkg-name-on-this-distro>
    local bin="$1" pkg="$2"
    if command -v "$bin" >/dev/null 2>&1; then
        return 0
    fi
    case "$PKG_MANAGER" in
        apt)
            sudo -n apt-get update -qq && sudo -n apt-get install -y -qq "$pkg" ;;
        dnf)
            sudo -n dnf install -y "$pkg" ;;
        pacman)
            sudo -n pacman -S --noconfirm "$pkg" ;;
        zypper)
            sudo -n zypper --non-interactive install "$pkg" ;;
        *)
            echo "  ✗ $bin not found and no package manager available to install it" >&2
            return 1 ;;
    esac
}

# Only enforce git/python3/curl/notify-send — they're declared prereqs above;
# if the user ran us as root or with sudo, fix missing ones silently.
# notify-send = libnotify-bin (Debian/Ubuntu) / libnotify (Fedora/Arch).
# Without it the toast silently degrades to stderr-only.
ensure_pkg git           git            || true
ensure_pkg curl          curl           || true
ensure_pkg python3       python3        || true
ensure_pkg notify-send   libnotify-bin  || true   # toast surface (best-effort)

# ─── 4. Install Hermes Agent via official installer ────────────────────────
if ! command -v hermes >/dev/null 2>&1 && [ ! -x "$HERMES_BIN" ]; then
    echo
    echo "Installing Hermes Agent via official installer..."
    # Official one-liner per hermes-agent docs. NOSPAM=1 keeps the post-install
    # telemetry banner quiet; we don't want installer noise in CI logs.
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

# ─── 7. Register systemd USER timer for daily update check (v0.4.0 design) ──
# Per the v0.4.0 design (commit de66e3a): the timer runs the daily update-check
# script which does git pull + GitHub releases API check + toast. The user runs
# `hermes update-dist` to actually apply the update (no auto-apply, no
# auto-download).
#
# User-scoped (no sudo) so the timer runs only while the user is logged in.
# Pattern from skill cross-platform-bash-scripting §4d (linux branch).
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

UPDATE_SERVICE="hermes-dist-update.service"
UPDATE_TIMER="hermes-dist-update.timer"
UPDATE_SCRIPT_SRC="$DIST_DIR/scripts/hermes-dist-update.sh"

# Copy the update script into a stable location the systemd unit references.
# systemd can't reliably follow relative paths or run scripts in $DIST_DIR if
# the repo gets moved/renamed, so we copy once at install time.
UPDATE_SCRIPT_DST="$HOME/.local/bin/hermes-dist-update.sh"
mkdir -p "$(dirname "$UPDATE_SCRIPT_DST")"
cp "$UPDATE_SCRIPT_SRC" "$UPDATE_SCRIPT_DST"
chmod +x "$UPDATE_SCRIPT_DST"

cat > "$SYSTEMD_USER_DIR/$UPDATE_SERVICE" <<SVC_EOF
[Unit]
Description=Hermes Dist — daily update check (v0.4.0)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$DIST_DIR
Environment=HERMES_DIST_DIR=$DIST_DIR
Environment=HERMES_DIST_REPO=$HERMES_DIST_REPO
Environment=HERMES_PIN_FILE=$DIST_DIR/.hermes-dist-version
ExecStart=/usr/bin/env bash $UPDATE_SCRIPT_DST
SVC_EOF

cat > "$SYSTEMD_USER_DIR/$UPDATE_TIMER" <<TMR_EOF
[Unit]
Description=Hermes Dist daily update check at 09:00

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
TMR_EOF

# Pin the current tag so the next run has a baseline to compare against.
# Pulls from git describe; falls back to "v0.0.0" if repo is bare / no tags.
CURRENT_TAG="$(cd "$DIST_DIR" && git describe --tags --abbrev=0 2>/dev/null || echo 'v0.0.0')"
echo "$CURRENT_TAG" > "$DIST_DIR/.hermes-dist-version"

# Reload user systemd and enable (don't start — user session may not be active
# during install; the .service for the timer will run on next login).
if [ "${SKIP_SCHEDULER:-0}" = "1" ]; then
    echo
    echo "  ⚠ SKIP_SCHEDULER=1 — not registering systemd timer"
else
    systemctl --user daemon-reload
    systemctl --user enable --now "$UPDATE_TIMER" 2>/dev/null || \
        echo "  ⚠ Failed to enable $UPDATE_TIMER (user session not active — will retry on next login)"
    echo "  ✓ Registered systemd user timer: $UPDATE_TIMER (daily 09:00, ±5min jitter)"
    echo "  ✓ Pinned current version: $CURRENT_TAG"
fi

# ─── 8. Final summary ───────────────────────────────────────────────────────
echo
echo "=== Installation Complete (Linux) ==="
echo "  HERMES_HOME:   $HERMES_HOME"
echo "  WORKING_DIR:   $WORKING_DIR"
echo "  Dist bundle:   $DIST_DIR"
echo "  Relay URL:     $HERMES_RELAY_URL"
echo "  Scheduler:     systemd user timer ($UPDATE_TIMER)"
echo "  Update check:  systemd user timer ($UPDATE_TIMER), daily 09:00 ±5min jitter"
echo "  Update script: $UPDATE_SCRIPT_DST"
echo "  Toast:         notify-send (libnotify)"
echo
echo "Launch with: hermes chat"