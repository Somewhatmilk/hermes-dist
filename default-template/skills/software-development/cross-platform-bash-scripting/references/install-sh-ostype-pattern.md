# install.sh OSTYPE extension pattern

> **Read this when:** writing or extending `install/install.sh` (or any
> "setup a hermes environment from scratch" script) for cross-OS support.

## The base pattern (already in SKILL.md §2-3)

The skill's main file covers path resolution and env-var defaulting. This
reference adds the **install-script-specific extension** for prereq install
and verification.

## Prereq install per OS

```bash
# === Step 1: install prereqs (OS-dispatched) ===
install_prereqs() {
    log "STEP 1: prereqs ($PACKAGE_MGR_PREREQ: git, gh, age, docker)"
    if [ "$VERIFY_ONLY" -eq 1 ]; then
        log "  [verify] would run: $PREREQ_INSTALL"
        return
    fi

    case $OS in
        windows)
            if ! command -v scoop >/dev/null 2>&1; then
                log "  scoop not found. Install: https://scoop.sh"
                printf "  Install scoop now? [y/N] "
                read -r yn
                [[ "$yn" =~ ^[Yy]$ ]] || { log "  abort: scoop required"; exit 1; }
                powershell -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser; iwr -useb get.scoop.sh | iex"
            fi
            ;;
        mac)
            if ! command -v brew >/dev/null 2>&1; then
                log "  brew not found. Install: https://brew.sh"
                # Don't auto-install brew — it requires sudo and user choice
                # about analytics. Just fail with a clear message.
                exit 1
            fi
            # Colima is Mac's docker-desktop alternative (no Docker Desktop
            # license needed for personal use).
            ;;
        linux)
            log "  using apt (or override PREREQ_INSTALL for your distro)"
            ;;
    esac

    # Install only what's missing (avoid full reinstall)
    local missing=()
    for cmd in git gh age docker; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done
    [ ${#missing[@]} -eq 0 ] && { log "  all prereqs already installed"; return; }
    log "  missing: ${missing[*]}"
    log "  running: $PREREQ_INSTALL"
    bash -c "$PREREQ_INSTALL" || { log "  ERROR: prereq install failed"; exit 1; }
}
```

**Key points:**
- Per-OS first-time setup (scoop install prompt, brew detection) is
  different from per-OS install command. Separate them clearly.
- `missing=()` + `bash -c "$PREREQ_INSTALL"` lets you reuse the same
  `missing[]` array for logging AND for the install command.
- On Mac, `brew install docker colima` is the standard pattern — colima
  replaces Docker Desktop (no license needed).

## PREREQ_INSTALL per OS (set in the OS case)

```bash
case $OS in
    windows) PREREQ_INSTALL='scoop install git gh age docker' ;;
    mac)     PREREQ_INSTALL='brew install git gh age docker colima' ;;
    linux)   PREREQ_INSTALL='sudo apt install -y git age docker.io docker-compose-plugin' ;;
esac
```

**Note `gh` is missing from the Linux line.** Reason: `gh` is not in apt's
default repos on most distros; users install it via GitHub's own apt repo.
Either drop the requirement on Linux (suggest `gh auth login` after the
fact) or document the repo-add step.

## OS-detection override (for tests + WSL)

```bash
detect_os() {
    # Allow forcing via env for CI, WSL quirks, or portability tests.
    if [ -n "${HERMES_INSTALL_OS:-}" ]; then
        echo "${HERMES_INSTALL_OS}"
        return
    fi
    if [[ "${OSTYPE:-}" == "msys" || "${OSTYPE:-}" == "cygwin" ]] \
        && [ -z "${HERMES_INSTALL_FALLBACK_LINUX:-}" ]; then
        echo "windows"
    elif [ -n "${WINDIR:-}" ] && [ -z "${HERMES_INSTALL_FALLBACK_LINUX:-}" ]; then
        echo "windows"
    elif [[ "${OSTYPE:-}" == "darwin"* ]]; then
        echo "mac"
    elif [[ "${OSTYPE:-}" == "linux"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}
```

The `HERMES_INSTALL_FALLBACK_LINUX` env var lets you force "this is Linux"
even when bash thinks it's Windows (e.g., running MSYS bash inside WSL).

## Venv path per OS

```bash
case $OS in
    windows) HERMES_VENV_BIN="$HERMES_HOME/hermes-agent/venv/Scripts" ;;
    mac)     HERMES_VENV_BIN="$HERMES_HOME/hermes-agent/venv/bin"   ;;
    linux)   HERMES_VENV_BIN="$HERMES_HOME/hermes-agent/venv/bin"   ;;
esac
```

Then `source "$HERMES_VENV_BIN/activate"` works on all three. The exe
suffix (`hermes.exe` vs `hermes`) is handled by the PATH itself.

## The `cmd //c` Windows-only trap (re-stated for install scripts)

`install/install.sh` runs `cmd //c "rmdir /s /q profiles"` to remove a
profile dir that's locked by a live hermes SQLite WAL file (Windows-native
rmdir is more forgiving than MSYS rm-rf for held handles). On Mac/Linux,
this is a syntax error.

**Pattern:**
```bash
case "${OSTYPE:-}" in
    msys*|cygwin*) cmd //c "rmdir /s /q profiles" 2>/dev/null || true ;;
    *)             rm -rf profiles/ 2>/dev/null || true ;;
esac
```

**Never** call `cmd //c` unconditionally. Even with `2>/dev/null`, the
shell will exit non-zero on the `cmd: not found` error from non-Windows
shells, and `set -e` will kill the script.