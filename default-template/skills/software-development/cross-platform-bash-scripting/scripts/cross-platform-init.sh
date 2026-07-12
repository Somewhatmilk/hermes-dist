#!/usr/bin/env bash
# Cross-platform-init.sh — reference implementation of the
# "OSTYPE case → _USER_DIR → env-var default → main work" pattern.
# Copy this skeleton into a new bash script under
# $HERMES_HOME/scripts/ or $OCD_DIR/, then replace the "MAIN WORK"
# section with your actual logic.
#
# Pattern reference: ~/.hermes/skills/software-development/cross-platform-bash-scripting/SKILL.md
set -euo pipefail

# === 1. PATH RESOLUTION via OSTYPE case ===
case "${OSTYPE:-}" in
    msys*|cygwin*)
        _USER_DIR="$HOME"
        _HERMES_EXE_SUBDIR="hermes-agent/venv/Scripts"
        _HERMES_EXE_NAME="hermes.exe"
        ;;
    darwin*|linux*)
        _USER_DIR="$HOME"
        _HERMES_EXE_SUBDIR="hermes-agent/venv/bin"
        _HERMES_EXE_NAME="hermes"
        ;;
    *)
        echo "ERROR: unsupported OS '$OSTYPE'. Edit this script to add it." >&2
        exit 1
        ;;
esac

# === 2. ENV-VAR OVERRIDE + default fallback ===
# Pattern: `: "${VAR:=default}"` — colon is required (set -u safe).
: "${HERMES_HOME:=$_USER_DIR/.hermes}"
MNEMOSYNE_HERMES="$HERMES_HOME/$_HERMES_EXE_SUBDIR/$_HERMES_EXE_NAME"

# === 3. LOGGING HELPER (always available, never undefined) ===
_ts() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(_ts)] $*" >&2; }

log "===== SCRIPT START ====="
log "OSTYPE=${OSTYPE:-<unset>}"
log "HERMES_HOME=$HERMES_HOME"
log "MNEMOSYNE_HERMES=$MNEMOSYNE_HERMES"

# === 4. MAIN WORK (OS-agnostic) ===
# Replace this section with your actual logic. The path variables
# above work on all 3 OSes.

if [ -x "$MNEMOSYNE_HERMES" ]; then
    log "hermes binary found"
else
    log "WARN: hermes not at $MNEMOSYNE_HERMES — activate venv first?"
fi

log "===== SCRIPT DONE ====="