#!/usr/bin/env bash
# install-unix.sh — Hermes Dist installer for Linux.
# Supports Debian/Ubuntu, Fedora/RHEL, Arch, and Alpine.
# Detects distro via /etc/os-release, then dispatches to the appropriate
# package manager.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Somewhatmilk/hermes-dist/master/install-unix.sh | bash
#   # or, with explicit relay:
#   HERMES_RELAY_URL=https://relay.example.com bash install-unix.sh
#   # or with explicit repo:
#   HERMES_DIST_REPO=https://github.com/Somewhatmilk/hermes-dist.git bash install-unix.sh
#
# Idempotent: re-running this on a machine that already has hermes-dist
# will refresh the dist repo + heartbeat schedule, but skip the user-creating
# steps. Use --reinstall to force.

set -euo pipefail

# ── Resolve script directory + source the shared common lib ──────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=install-common/common.sh
source "$SCRIPT_DIR/install-common/common.sh"

# ── 0. Detect distribution + privilege model ────────────────────────────
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_FAMILY="${ID_LIKE:-unknown}"
    else
        DISTRO_ID="unknown"
        DISTRO_FAMILY="unknown"
    fi
}

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

# ── Package manager wrappers ─────────────────────────────────────────────
have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_pkg() {
    case "$DISTRO_FAMILY" in
        *debian*|*ubuntu*)
            run_priv apt-get update -qq && run_priv apt-get install -y -qq "$@" ;;
        *fedora*|*rhel*|*centos*)
            run_priv dnf install -y "$@" ;;
        *arch*)
            run_priv pacman -Sy --noconfirm "$@" ;;
        *alpine*)
            run_priv apk add --no-cache "$@" ;;
        *)
            log_warn "Unknown distro family '$DISTRO_FAMILY'. Please install '$*' manually."
            return 1 ;;
    esac
}

# ── Logging wrappers ────────────────────────────────────────────────────
log_info()  { printf "  \033[0;32m✓\033[0m %s\n" "$*"; }
log_warn()  { printf "  \033[0;33m⚠\033[0m %s\n" "$*" >&2; }
log_error() { printf "  \033[0;31m✗\033[0m %s\n" "$*" >&2; }
die()       { log_error "$*"; exit 1; }
run()       { "$@"; }

# ── OS-specific hermes_home + paths ──────────────────────────────────────
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
        echo "$HOME/.local/bin/hermes"
    fi
}

# ── OS-specific startup task registration ───────────────────────────────
add_startup_task() {
    local task_name="$1"; shift
    local cmd="$1"; shift
    local interval="${1:-30}"; shift || true
    local extra_args=("$@")

    if have_cmd systemctl && [ -d /run/systemd/system ]; then
        # systemd --user timer
        local unit_dir="$HOME/.config/systemd/user"
        mkdir -p "$unit_dir"
        local service_file="$unit_dir/hermes-dist-${task_name}.service"
        local timer_file="$unit_dir/hermes-dist-${task_name}.timer"

        cat > "$service_file" <<EOF
[Unit]
Description=Hermes Dist $task_name

[Service]
Type=oneshot
ExecStart=$cmd ${extra_args[*]}
Environment=HERMES_HOME=$(hermes_home)
EOF
        cat > "$timer_file" <<EOF
[Unit]
Description=Run $task_name every ${interval}s

[Timer]
OnBootSec=30s
OnUnitActiveSec=${interval}s
AccuracySec=5s
Persistent=true

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now "hermes-dist-${task_name}.timer" \
            && log_info "  ✓ systemd timer installed: $task_name" \
            || log_warn "  ⚠ Failed to enable systemd timer: $task_name"
    elif have_cmd crontab; then
        # Cron fallback
        local cron_expr
        if [ "$interval" -lt 60 ]; then
            cron_expr="* * * * *"  # every minute; the script self-throttles
        else
            local mins=$((interval / 60))
            cron_expr="*/$mins * * * *"
        fi
        ( crontab -l 2>/dev/null | grep -v "hermes-dist-$task_name" || true
          echo "$cron_expr $cmd ${extra_args[*]} # hermes-dist-$task_name" ) | crontab -
        log_info "  ✓ crontab entry installed: $task_name"
    else
        log_warn "No systemd or crontab. Skipping background task: $task_name"
        log_warn "  User must run '$cmd ${extra_args[*]}' manually each session."
    fi
}

# ── Main flow ────────────────────────────────────────────────────────────
main() {
    log_info "=== Hermes Dist Installer — Linux ==="
    log_info ""

    detect_distro
    log_info "Detected: $DISTRO_ID (family: $DISTRO_FAMILY)"

    HERMES_HOME="$(hermes_home)"
    export HERMES_HOME
    log_info "Hermes home: $HERMES_HOME"

    preflight
    install_hermes_if_missing

    # Ensure python3 has the 'flock' util for heartbeat locking
    case "$DISTRO_FAMILY" in
        *alpine*) install_pkg util-linux ;;
    esac

    local repo_url="${HERMES_DIST_REPO:-$HERMES_DIST_REPO_DEFAULT}"
    local dist_dir="$HOME/hermes-dist"
    ensure_dist_repo "$repo_url" "$dist_dir"

    local relay_url="${HERMES_RELAY_URL:-https://relay.local}"
    run_onboard "$dist_dir" "$relay_url"
    register_heartbeat "$dist_dir" "$relay_url"
    register_daily_pull "$dist_dir"
    maybe_install_tinysearch
    print_summary "$dist_dir" "$relay_url"
}

main "$@"
