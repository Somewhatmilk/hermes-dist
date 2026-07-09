# install-common — Shared code for hermes-dist installers.
#
# All three installers (Windows PowerShell, macOS bash, Linux bash) include
# this file. The exact mechanism differs per OS:
#
#   - install-windows.ps1  inlines the logic at build time (PowerShell can't
#                          source a shared module reliably across PS editions)
#   - install-macos.sh     sources this file via SCRIPT_DIR resolution
#   - install-unix.sh      sources this file via SCRIPT_DIR resolution
#
# The contract: each installer defines these shell-native wrappers BEFORE
# sourcing this file:
#
#   log_info   <msg>
#   log_warn   <msg>
#   log_error  <msg>
#   die        <msg>        # log_error + exit 1
#   run        <cmd>        # execute a command, return its stdout
#   sudo       <cmd>        # run a command with root (no-op if already root)
#   have_cmd   <name>       # return 0 if command exists, 1 otherwise
#   install_pkg <name>      # OS-native package install (apt/brew/dnf/pacman)
#   user_config_dir         # XDG_CONFIG_HOME or OS equivalent
#   user_data_dir           # XDG_DATA_HOME or OS equivalent
#   hermes_home             # ~/.hermes on unix, %USERPROFILE%\.hermes on win
#   hermes_bin              # path to hermes executable
#   add_startup_task        # register OS-native background task
#
# This file then provides the higher-level flow that all installers use.
# Don't put anything OS-specific in here.

# ── Constants ──────────────────────────────────────────────────────────────
HERMES_DIST_VERSION="0.2.0"
HERMES_DIST_REPO_DEFAULT="https://github.com/Somewhatmilk/hermes-dist.git"
HERMES_DIST_HEARTBEAT_INTERVAL_SEC=30
HERMES_DIST_HEARTBEAT_JITTER_SEC=10

# ── Common preflight checks ───────────────────────────────────────────────
preflight() {
    log_info "Checking prerequisites..."

    # Python 3.11+ (cross-OS: try python3, then python)
    local py=""
    if have_cmd python3; then
        py="python3"
    elif have_cmd python; then
        py="python"
    fi
    if [ -z "$py" ]; then
        die "Python 3.11+ not found. Install Python from https://python.org/downloads/"
    fi
    local ver
    ver=$($py -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    case "$ver" in
        3.1[1-9]|3.[2-9][0-9]|4.*) log_info "  ✓ Python $ver" ;;
        *) die "Python $ver is too old. Need 3.11+." ;;
    esac
    PYTHON_BIN="$py"

    if have_cmd git; then
        log_info "  ✓ Git: $(git --version | head -1)"
    else
        die "Git not found."
    fi
}

# ── Install Hermes Agent if missing ───────────────────────────────────────
install_hermes_if_missing() {
    if have_cmd hermes; then
        log_info "  ✓ Hermes already installed: $(hermes version 2>&1 | head -1)"
        return 0
    fi
    log_info "Installing Hermes Agent via official installer..."
    if have_cmd curl; then
        curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    elif have_cmd wget; then
        wget -qO- https://hermes-agent.nousresearch.com/install.sh | bash
    else
        die "Neither curl nor wget available. Install one and retry."
    fi
}

# ── Clone or update the dist repo ─────────────────────────────────────────
ensure_dist_repo() {
    local repo_url="$1"
    local target_dir="$2"

    if [ -d "$target_dir/.git" ]; then
        log_info "  ✓ Using existing $target_dir"
        # Pull the latest — safe because operator files are 444 / read-only
        # from the user's perspective. (The OS-level read-only is per-profile,
        # not per-repo; a git pull will fail on chmod 444 files. We use
        # --no-edit + a temp umask to bypass that.)
        (cd "$target_dir" && git fetch --depth=1 origin master 2>&1 | head -5) || true
    else
        log_info "Cloning $repo_url → $target_dir"
        run git clone --depth=1 "$repo_url" "$target_dir"
    fi
}

# ── Run first-launch onboarding ──────────────────────────────────────────
run_onboard() {
    local dist_dir="$1"
    local relay_url="$2"

    if [ ! -f "$dist_dir/.onboard.sh" ]; then
        die ".onboard.sh not found in $dist_dir"
    fi

    export HERMES_HOME
    export HERMES_DIST_REPO
    export HERMES_RELAY_URL="$relay_url"

    log_info "Running first-launch onboarding..."
    # On Windows the installer is .ps1 and bash is Git Bash; on unix, this is native bash.
    bash "$dist_dir/.onboard.sh"
}

# ── Register heartbeat (push-update channel) ─────────────────────────────
register_heartbeat() {
    local dist_dir="$1"
    local relay_url="$2"

    # Heartbeat client script lives in install-common; symlink into dist repo
    # so a single source of truth can be updated by the operator.
    local hb_src="$dist_dir/install-common/heartbeat.sh"
    local hb_dst="$HERMES_HOME/.hermes-dist-heartbeat.sh"

    if [ ! -f "$hb_src" ]; then
        log_warn "heartbeat.sh not found in $dist_dir/install-common/ — push updates disabled"
        return 0
    fi

    cp "$hb_src" "$hb_dst"
    chmod 555 "$hb_dst"

    add_startup_task "HermesDistHeartbeat" "$hb_dst" \
        "$relay_url" "$HERMES_DIST_HEARTBEAT_INTERVAL_SEC"
}

# ── Register daily git pull for dist repo updates ─────────────────────────
register_daily_pull() {
    local dist_dir="$1"
    add_startup_task "HermesDistDailyUpdate" \
        "cd '$dist_dir' && git pull --ff-only" "86400"
}

# ── Tinysearch opt-in (web-scraping companion) ───────────────────────────
maybe_install_tinysearch() {
    if ! have_cmd docker; then
        log_warn "Docker not found. tinysearch companion will not start. Web scraping falls back to direct HTTP."
        return 0
    fi
    if docker ps -a --filter "name=hermes-tinysearch" --format "{{.Names}}" 2>/dev/null | grep -q hermes-tinysearch; then
        log_info "  ✓ tinysearch container already exists"
        docker start hermes-tinysearch 2>/dev/null || true
    else
        log_info "Starting tinysearch container..."
        docker pull hermes/tinysearch:latest 2>/dev/null || log_warn "Could not pull hermes/tinysearch image"
        docker run -d --name hermes-tinysearch \
            -p 127.0.0.1:8000:8000 \
            --restart unless-stopped \
            hermes/tinysearch:latest 2>/dev/null \
            || log_warn "tinysearch failed to start (non-fatal)"
    fi
}

# ── Final summary ────────────────────────────────────────────────────────
print_summary() {
    local dist_dir="$1"
    local relay_url="$2"
    log_info "=== Installation Complete ==="
    log_info "  Hermes home:    $HERMES_HOME"
    log_info "  Dist bundle:    $dist_dir"
    log_info "  Relay URL:      $relay_url"
    log_info ""
    log_info "Launch with: hermes"
    log_info "Or run the desktop app."
}
