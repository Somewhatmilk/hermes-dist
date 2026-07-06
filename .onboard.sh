#!/usr/bin/env bash
# .onboard.sh — runs ONCE on first launch of a hermes-dist install.
# Generates user UUID, configures opt-in, wires hooks, registers with relay.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE_NAME="default-template"
PROFILE_DIR="$HERMES_HOME/profiles/$PROFILE_NAME"
DIST_REPO="${HERMES_DIST_REPO:-}"

echo "=== Hermes Dist PoC — First Launch Onboarding ==="
echo

# ─── 1. Generate user UUID ─────────────────────────────────────────────────
USER_UUID=$("$PROFILE_DIR/scripts/uuidgen.sh")
echo "Generated UUID: $USER_UUID"
echo "$USER_UUID" > "$HERMES_HOME/.user_id"
chmod 600 "$HERMES_HOME/.user_id"

# ─── 2. Rename the profile to the UUID ────────────────────────────────────
# This ensures no two users can collide on "default-template" if multiple
# installs share a machine.
NEW_PROFILE_NAME="$USER_UUID"
NEW_PROFILE_DIR="$HERMES_HOME/profiles/$NEW_PROFILE_NAME"

if [ "$PROFILE_NAME" != "$NEW_PROFILE_NAME" ]; then
  echo "Renaming profile $PROFILE_NAME → $NEW_PROFILE_NAME"
  # Update profile.yaml's name field
  sed -i.bak "s/^name: $PROFILE_NAME$/name: $NEW_PROFILE_NAME/" "$PROFILE_DIR/profile.yaml"
  rm -f "$PROFILE_DIR/profile.yaml.bak"
  # Move directory
  mv "$PROFILE_DIR" "$NEW_PROFILE_DIR"
  PROFILE_DIR="$NEW_PROFILE_DIR"
fi

# ─── 3. Lock down operator-owned files (chmod 444 = read-only) ────────────
# The user CANNOT modify these. The hook scripts, the denylist, the SOUL.md.
echo "Locking down operator files (chmod 444)..."
chmod 444 "$PROFILE_DIR/SOUL.md"
chmod 444 "$PROFILE_DIR/security/denylist.yaml"
chmod 444 "$PROFILE_DIR/security/allowlist.yaml"
chmod 555 "$PROFILE_DIR/hooks/"*.sh
chmod 555 "$PROFILE_DIR/scripts/"*.sh
chmod 555 "$PROFILE_DIR/scripts/"

# ─── 4. Generate HMAC auth token ──────────────────────────────────────────
AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "Generated auth token (HMAC-SHA256)"
echo "$AUTH_TOKEN" > "$HERMES_HOME/.auth_token"
chmod 600 "$HERMES_HOME/.auth_token"

# ─── 5. Prompt for opt-in ─────────────────────────────────────────────────
echo
echo "=== Data Collection Opt-In ==="
echo "This hermes-dist install can optionally forward certain events to the"
echo "operator's collector. Events forwarded are:"
echo "  - Skills you create (clean ones queued for review; flagged ones sent immediately)"
echo "  - Memories you mark with submit_to_collector: true"
echo "  - Scripts that match the security denylist (sent immediately, blocked from running)"
echo
echo "If you opt out, NO data leaves this machine. You can change this later by"
echo "editing $PROFILE_DIR/config.yaml (mnemosyne.sync.enabled)."
echo

read -r -p "Opt in to data forwarding? [y/N] " OPTIN
OPTIN=$(echo "$OPTIN" | tr '[:upper:]' '[:lower:]')

if [[ "$OPTIN" == "y" || "$OPTIN" == "yes" ]]; then
  SYNC_ENABLED=true
  echo
  read -r -p "Operator relay URL (default: https://relay.local): " RELAY_URL
  RELAY_URL="${RELAY_URL:-https://relay.local}"
else
  SYNC_ENABLED=false
  RELAY_URL=""
fi

# ─── 6. Update config.yaml with opt-in / UUID / token ─────────────────────
echo "Writing config..."
python3 << EOF
import re, sys

config_path = "$PROFILE_DIR/config.yaml"
with open(config_path, 'r', encoding='utf-8') as f:
    config = f.read()

# Update memory sync block
sync_block = f"""memory:
  provider: mnemosyne
  mnemosyne:
    sync:
      enabled: {str($SYNC_ENABLED).lower()}
      remote: "$RELAY_URL"
      device_id: "$USER_UUID"
      auth_token: "$AUTH_TOKEN"
      push_on_session_end: {str($SYNC_ENABLED).lower()}
      push_interval_minutes: 30
      pull_on_session_start: false"""

config = re.sub(
    r'memory:\s*\n\s*provider: mnemosyne\s*\n\s*mnemosyne:[\s\S]*?pull_on_session_start: false',
    sync_block,
    config,
    flags=re.MULTILINE
)

# Update update channel
if "$DIST_REPO":
    config = re.sub(
        r'update:\s*\n\s*channel: ""',
        f'update:\n  channel: "$DIST_REPO"',
        config
    )

with open(config_path, 'w', encoding='utf-8') as f:
    f.write(config)

print("Config updated.")
EOF

# ─── 7. Wire up hooks (copy to .hermes/hooks/ for hermes to find) ─────────
HOOKS_DEST="$HERMES_HOME/hooks"
mkdir -p "$HOOKS_DEST"
cp "$PROFILE_DIR/hooks/pre-tool.sh" "$HOOKS_DEST/"
cp "$PROFILE_DIR/hooks/post-skill-create.sh" "$HOOKS_DEST/"
cp "$PROFILE_DIR/hooks/post-memory-save.sh" "$HOOKS_DEST/"
chmod 555 "$HOOKS_DEST/"*.sh

# ─── 8. Create audit + quarantine + queue dirs ────────────────────────────
mkdir -p "$HERMES_HOME/audit"
mkdir -p "$HERMES_HOME/quarantine/skills/clean" "$HERMES_HOME/quarantine/skills/flagged"
mkdir -p "$HERMES_HOME/queue/memories" "$HERMES_HOME/queue/skills"
touch "$HERMES_HOME/audit.log"
chmod 600 "$HERMES_HOME/audit.log"

# ─── 9. If opted in, register with relay ──────────────────────────────────
if [ "$SYNC_ENABLED" = "true" ] && [ -n "$RELAY_URL" ]; then
  echo
  echo "Registering with relay at $RELAY_URL..."
  REG_BODY=$(cat <<EOF
{
  "uuid": "$USER_UUID",
  "os": "$(uname -s 2>/dev/null || echo unknown)",
  "version": "hermes-dist-poc-1.0.0",
  "opted_in": true,
  "registered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
  HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/register" \
    -H "Content-Type: application/json" \
    -H "X-Hermes-User: $USER_UUID" \
    -H "X-Hermes-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -d "$REG_BODY" \
    --max-time 15 \
    --retry 2 \
    2>&1 || echo "000")

  if [[ "$HTTP_CODE" =~ ^2 ]]; then
    echo "✓ Registered with relay (HTTP $HTTP_CODE)"
  else
    echo "⚠ Relay registration failed (HTTP $HTTP_CODE). Sync will retry automatically."
  fi
fi

# ─── 10. Final summary ─────────────────────────────────────────────────────
echo
echo "=== Onboarding Complete ==="
echo "  Profile name:    $NEW_PROFILE_NAME"
echo "  UUID:            $USER_UUID"
echo "  Data forwarding: $SYNC_ENABLED"
echo "  Relay URL:       ${RELAY_URL:-(none)}"
echo
echo "Launch with: hermes -p $NEW_PROFILE_NAME chat"
echo "Or in the desktop app, this profile will be selected by default."
