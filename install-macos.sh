#!/usr/bin/env bash
# install-macos.sh — Hermes Dist installer for macOS.
# Supports Apple Silicon (arm64) and Intel (x86_64), and macOS 12+ (Monterey).
# Uses Homebrew for package install + launchd for background tasks.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Somewhatmilk/hermes-dist/master/install-macos.sh | bash
#   HERMES_RELAY_URL=https://relay.example.com bash install-macos.sh
#   HERMES_DIST_REPO=https://github.com/Somewhatmilk/hermes-dist.git bash install-macos.sh
#
# Note: this installs Hermes Agent via Homebrew (`brew install hermes`).
# If you'd rather use the .dmg-based GUI installer, see packaging/darwin/.
#
# Code signing + notarization: this script does NOT sign the resulting
# install. For a signed .dmg workflow, use packaging/darwin/build-dmg.sh
# (requires Apple Developer ID + notarytool credentials).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=install-common/common.sh
source "$SCRIPT_DIR/install-common/common.sh"

# ── macOS detection + privilege model ───────────────────────────────────
is_root() { [ "$(id -u)" -eq 0 ]; }
# NOTE: do not name this `sudo` — would shadow the binary and recurse forever.
run_priv() {
    if is_root; then
        "$@"
    else
        command -v sudo >/dev/null 2>&1 || die "sudo not available and we are not root"
        sudo "$@"
    fi
}

# macOS doesn't ship with `flock`; we use a directory-as-lockfile trick.
have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_pkg() {
    if ! have_cmd brew; then
        log_warn "Homebrew not installed. Install from https://brew.sh first."
        log_warn "Cannot auto-install: $*"
        return 1
    fi
    brew install "$@"
}

log_info()  { printf "  \033[0;32m✓\033[0m %s\n" "$*"; }
log_warn()  { printf "  \033[0;33m⚠\033[0m %s\n" "$*" >&2; }
log_error() { printf "  \033[0;31m✗\033[0m %s\n" "$*" >&2; }
die()       { log_error "$*"; exit 1; }
run()       { "$@"; }

hermes_home() {
    if [ -n "${HERMES_HOME:-}" ]; then
        echo "$HERMES_HOME"
    else
        echo "$HOME/.hermes"
    fi
}
hermes_bin() {
    if have_cmd hermes; then
        command -v hermes
    else
        echo "$(brew --prefix)/bin/hermes"
    fi
}

# ── launchd task registration (preferred over cron on macOS) ─────────────
# $1: label (reverse-DNS, e.g. com.somew.hermes-dist.heartbeat)
# $2: program to run
# $3..: extra args
add_startup_task() {
    local task_name="$1"; shift
    local cmd="$1"; shift
    local interval="${1:-30}"; shift || true
    local extra_args=("$@")

    local label="com.somew.hermes-dist.$(printf '%s' "$task_name" | tr '[:upper:]' '[:lower:]')"
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/$label.plist"

    mkdir -p "$plist_dir"

    # Build ProgramArguments array (launchd requires array form, not shell string)
    local prog_args
    prog_args=$(python3 -c "
import sys, json
args = ['$cmd'] + $(printf '%s\n' "${extra_args[@]:-}" | python3 -c '
import sys
lines = [l.rstrip() for l in sys.stdin if l.strip()]
print(json.dumps(lines))
' 2>/dev/null || echo '[]')
print(json.dumps(args))
")

    cat > "$plist_file" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
        <string>$cmd</string>
$(printf '        <string>%s</string>\n' "${extra_args[@]:-}")
    </array>
    <key>StartInterval</key>
    <integer>$interval</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/hermes-dist-$task_name.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/hermes-dist-$task_name.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HERMES_HOME</key>
        <string>$(hermes_home)</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

    # launchctl load it
    launchctl unload "$plist_file" 2>/dev/null || true
    launchctl load "$plist_file" 2>/dev/null \
        && log_info "  ✓ launchd agent installed: $label (every ${interval}s)" \
        || log_warn "  ⚠ launchctl load failed for $label"
}

# ── Main flow ────────────────────────────────────────────────────────────
main() {
    log_info "=== Hermes Dist Installer — macOS ==="
    log_info ""

    # macOS version check
    local macos_ver
    macos_ver=$(sw_vers -productVersion 2>/dev/null || echo "0.0")
    log_info "Detected: macOS $macos_ver (kernel: $(uname -m))"

    # Require macOS 12 (Monterey) for launchd v2 features we use
    case "$macos_ver" in
        12.*|13.*|14.*|15.*|16.*) ;;
        *) log_warn "macOS $macos_ver is older than 12.0 (Monterey). May work but is untested." ;;
    esac

    HERMES_HOME="$(hermes_home)"
    export HERMES_HOME
    log_info "Hermes home: $HERMES_HOME"

    preflight

    # macOS doesn't ship `flock`; use a different lockfile mechanism
    # in heartbeat.sh on this platform (or install it via brew install flock)
    if ! have_cmd flock; then
        log_warn "flock not found. Installing via Homebrew..."
        install_pkg flock || log_warn "  Install manually: brew install flock"
    fi

    install_hermes_if_missing

    local repo_url="${HERMES_DIST_REPO:-$HERMES_DIST_REPO_DEFAULT}"
    local dist_dir="$HOME/hermes-dist"
    ensure_dist_repo "$repo_url" "$dist_dir"

    local relay_url="${HERMES_RELAY_URL:-https://relay.local}"
    run_onboard "$dist_dir" "$relay_url"
    register_heartbeat "$dist_dir" "$relay_url"
    register_daily_pull "$dist_dir"

    # tinysearch on macOS: Docker Desktop needed. Skip if missing.
    if have_cmd docker; then
        maybe_install_tinysearch
    else
        log_warn "Docker Desktop not found. Skipping tinysearch companion."
        log_warn "  Install from https://www.docker.com/products/docker-desktop/ for shared web scraping."
    fi

    print_summary "$dist_dir" "$relay_url"
}

main "$@"
