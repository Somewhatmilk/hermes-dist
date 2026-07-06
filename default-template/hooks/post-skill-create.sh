#!/usr/bin/env bash
# ~/.hermes/profiles/default-template/hooks/post-skill-create.sh
#
# Runs AFTER a skill_manage create call. Scans the created skill's
# SKILL.md and any scripts/ against the denylist via scan_skill.py.
# Clean skills are quarantined for operator review. Flagged skills are
# quarantined + the local install is removed.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE_DIR="$HERMES_HOME/profiles/default-template"
DENYLIST="$PROFILE_DIR/security/denylist.yaml"
SCAN_SCRIPT="$PROFILE_DIR/hooks/scan_skill.py"
QUARANTINE="$HERMES_HOME/quarantine/skills"
AUDIT_LOG="$HERMES_HOME/audit.log"

mkdir -p "$QUARANTINE/clean" "$QUARANTINE/flagged"

SKILL_PATH="${HERMES_SKILL_PATH:-}"
if [ -z "$SKILL_PATH" ] || [ ! -d "$SKILL_PATH" ]; then
  echo "post-skill-create: no SKILL_PATH provided or path missing" >&2
  exit 0
fi

SKILL_NAME=$(basename "$SKILL_PATH")
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
USER_UUID="${HERMES_USER_UUID:-unknown}"

# Run the scan
if SCAN_OUTPUT=$(python3 "$SCAN_SCRIPT" "$DENYLIST" "$SKILL_PATH" 2>&1); then
    # Clean
    DEST="$QUARANTINE/clean/${USER_UUID}_${SKILL_NAME}_${TIMESTAMP}"
    cp -r "$SKILL_PATH" "$DEST"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SKILL_CLEAN uuid=$USER_UUID skill=$SKILL_NAME path=$DEST" >> "$AUDIT_LOG"

    # Forward to relay (best-effort)
    if [ -x "$HERMES_HOME/scripts/forward-sync.sh" ]; then
        "$HERMES_HOME/scripts/forward-sync.sh" \
            --type skill_clean \
            --uuid "$USER_UUID" \
            --payload "$DEST" || true
    fi
else
    SCAN_EXIT=$?
    # Flagged
    DEST="$QUARANTINE/flagged/${USER_UUID}_${SKILL_NAME}_${TIMESTAMP}"
    cp -r "$SKILL_PATH" "$DEST"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SKILL_FLAGGED uuid=$USER_UUID skill=$SKILL_NAME reason=\"$SCAN_OUTPUT\" path=$DEST" >> "$AUDIT_LOG"

    # Block the skill from being installed locally
    rm -rf "$SKILL_PATH"

    # Forward immediately to relay
    if [ -x "$HERMES_HOME/scripts/forward-sync.sh" ]; then
        "$HERMES_HOME/scripts/forward-sync.sh" \
            --type skill_flagged \
            --uuid "$USER_UUID" \
            --payload "$DEST" \
            --reason "$SCAN_OUTPUT" || true
    fi
fi

exit 0
