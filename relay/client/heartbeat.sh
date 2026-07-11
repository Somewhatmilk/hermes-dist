#!/usr/bin/env bash
# heartbeat.sh — T3 client-side push-update poller
#
# The user's hermes install runs this script every 60s. Each tick:
#   1. Build a HMAC-signed GET to /api/v1/profile-bundle?since=<last>
#   2. Send to the relay
#   3. Parse the response
#        - up_to_date=true  → nothing to do
#        - up_to_date=false → apply the new bundle (write SOUL.md + config.yaml)
#   4. Advance the local `since` pointer to server_time_unix
#   5. Persist the pointer so the next tick resumes where we left off
#
# Inputs (env vars or files under ~/.hermes/state/heartbeat/):
#   HERMES_RELAY_URL    e.g. http://127.0.0.1:9119 or https://host.tail.ts.net:9119
#   HERMES_USER_UUID    the user's registered UUID
#   HERMES_HMAC_SECRET  the user's per-install HMAC secret
#   HERMES_PROFILE_DIR  where to write SOUL.md and config.yaml
#                       (default: $HOME/.hermes/profiles/default)
#   HEARTBEAT_INTERVAL  seconds between polls (default: 60)
#   HEARTBEAT_ONCE      if set to 1, run a single poll + exit (handy for tests)
#
# The `since` pointer is persisted to
#   $HERMES_STATE_DIR/heartbeat/last_seen  (default ~/.hermes/state/heartbeat)
# so a reboot resumes from "what the user already has", not "epoch 0".
#
# HMAC canonical for this GET (must match the relay's
# verify_hmac_get_request byte-for-byte — see relay/app/hmac_auth.py):
#
#   <user_uuid>\n<timestamp>\n<nonce>\n<event_type>\nGET <path?query>
#
# This is the wire format the relay enforces, including the path+query
# so a captured signature for ?since=1000 cannot be replayed as
# ?since=2000. Do NOT "simplify" this canonical; any drift will
# silently 401 every request.
#
# Pitfall — sign the EXACT path+query the relay will see. The relay
# uses the raw query string in the order the client sent it. If you
# build the URL with multiple equivalent forms (?since=100&debug=1 vs
# ?debug=1&since=100) the hash differs. Stick to one form.
#
# Pitfall — the SOUL.md write overwrites whatever the user has in
# their profile. The operator's push is the source of truth. We back
# up the existing files to <path>.pre-heartbeat.bak first so the user
# can manually recover if the push is wrong.

set -euo pipefail

# ─── Config (env vars with sensible defaults) ─────────────────────────────
RELAY_URL="${HERMES_RELAY_URL:-http://127.0.0.1:9119}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/default}"
STATE_DIR="${HERMES_STATE_DIR:-$HOME/.hermes/state/heartbeat}"
INTERVAL="${HEARTBEAT_INTERVAL:-60}"
RUN_ONCE="${HEARTBEAT_ONCE:-0}"

# UUID + secret: env var wins, else read from a state file the install
# script wrote. The state-file path is canonical so the operator's
# `hermes-distribution` tooling can drop the secret in one place.
if [ -z "${HERMES_USER_UUID:-}" ] && [ -f "$STATE_DIR/user.uuid" ]; then
    HERMES_USER_UUID=$(cat "$STATE_DIR/user.uuid")
fi
if [ -z "${HERMES_HMAC_SECRET:-}" ] && [ -f "$STATE_DIR/user.secret" ]; then
    HERMES_HMAC_SECRET=$(cat "$STATE_DIR/user.secret")
fi

if [ -z "${HERMES_USER_UUID:-}" ] || [ -z "${HERMES_HMAC_SECRET:-}" ]; then
    echo "✗ HERMES_USER_UUID and HERMES_HMAC_SECRET must be set" >&2
    echo "  (or write them to $STATE_DIR/user.uuid + user.secret)" >&2
    exit 2
fi

EVENT_TYPE="profile_bundle"
LOG_PREFIX="[heartbeat $(date -u +%Y-%m-%dT%H:%M:%SZ)]"

mkdir -p "$PROFILE_DIR" "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true

# ─── Helpers ───────────────────────────────────────────────────────────────

# Build the HMAC-SHA256 signature as base64 (must match the relay's
# compute_signature in relay/app/hmac_auth.py).
sign_canonical() {
    # $1 = canonical string (no trailing newline)
    printf '%s' "$1" | openssl dgst -sha256 -hmac "$HERMES_HMAC_SECRET" -binary | base64 -w 0
}

# Read the last seen timestamp (0 if never run).
read_last_seen() {
    if [ -f "$STATE_DIR/last_seen" ]; then
        cat "$STATE_DIR/last_seen"
    else
        echo "0"
    fi
}

# Persist the last seen timestamp.
write_last_seen() {
    printf '%s' "$1" > "$STATE_DIR/last_seen"
}

# Apply a bundle to disk: back up + write soul.md + write config.yaml.
# Reloads hermes if a reload command is configured.
apply_bundle() {
    local bundle_json="$1"
    local version soul_md config_yaml toolsets_json

    version=$(echo "$bundle_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')
    soul_md=$(echo "$bundle_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["soul_md"])')
    config_yaml=$(echo "$bundle_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["config_yaml"])')
    toolsets_json=$(echo "$bundle_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["toolsets_json"])')

    echo "$LOG_PREFIX  → applying bundle version=$version"

    # Back up the existing files (if any) so the user can recover
    if [ -f "$PROFILE_DIR/SOUL.md" ]; then
        cp -p "$PROFILE_DIR/SOUL.md" "$PROFILE_DIR/SOUL.md.pre-heartbeat.bak"
    fi
    if [ -f "$PROFILE_DIR/config.yaml" ]; then
        cp -p "$PROFILE_DIR/config.yaml" "$PROFILE_DIR/config.yaml.pre-heartbeat.bak"
    fi

    printf '%s' "$soul_md"     > "$PROFILE_DIR/SOUL.md"
    printf '%s' "$config_yaml" > "$PROFILE_DIR/config.yaml"
    # toolsets_json is metadata; the operator's intent is that
    # hermes-config.yaml references it. We stash it as a sidecar
    # for inspection but the user's hermes reads the YAML list
    # from config.yaml.
    printf '%s' "$toolsets_json" > "$STATE_DIR/last_toolsets.json"

    echo "$LOG_PREFIX    wrote $PROFILE_DIR/SOUL.md ($(printf '%s' "$soul_md" | wc -c) bytes)"
    echo "$LOG_PREFIX    wrote $PROFILE_DIR/config.yaml ($(printf '%s' "$config_yaml" | wc -c) bytes)"

    # Optional reload hook: if the user has configured a reload command
    # (e.g. `hermes config reload` or `systemctl --user restart hermes`),
    # run it now. Default: log only. Wired up by the install script.
    if [ -n "${HERMES_RELOAD_CMD:-}" ]; then
        echo "$LOG_PREFIX    running reload: $HERMES_RELOAD_CMD"
        if ! bash -c "$HERMES_RELOAD_CMD" 2>&1; then
            echo "$LOG_PREFIX  ! reload command failed (bundle already on disk)" >&2
        fi
    fi
}

# Single poll: build signature, GET, parse, apply, update pointer.
poll_once() {
    local last_seen timestamp nonce path_and_query canonical signature
    last_seen=$(read_last_seen)
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    nonce=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
    # IMPORTANT: do not URL-encode the since value. The relay signs the
    # raw query string as it appeared on the wire; if we URL-encode
    # and curl re-encodes differently, the hash will mismatch.
    path_and_query="/api/v1/profile-bundle?since=$last_seen"

    # Canonical: <uuid>\n<ts>\n<nonce>\n<event_type>\nGET <path?query>
    canonical=$(printf '%s\n%s\n%s\n%s\n%s' \
        "$HERMES_USER_UUID" "$timestamp" "$nonce" "$EVENT_TYPE" \
        "GET $path_and_query")
    signature=$(sign_canonical "$canonical")

    # Capture body + status code. The relay uses 200 for both
    # "bundle found" and "up to date", and 401 for bad signature.
    local response http_code
    response=$(curl -sS -o "$STATE_DIR/last_response.json" -w "%{http_code}" \
        -X GET "$RELAY_URL$path_and_query" \
        -H "X-Hermes-User: $HERMES_USER_UUID" \
        -H "X-Hermes-Timestamp: $timestamp" \
        -H "X-Hermes-Nonce: $nonce" \
        -H "X-Hermes-Signature: $signature" \
        -H "X-Hermes-Event-Type: $EVENT_TYPE" \
        --max-time 15) || {
        echo "$LOG_PREFIX  ✗ curl failed (relay unreachable?)" >&2
        return 1
    }
    http_code="$response"

    if [ "$http_code" != "200" ]; then
        echo "$LOG_PREFIX  ✗ HTTP $http_code — $(head -c 200 "$STATE_DIR/last_response.json" 2>/dev/null)" >&2
        return 1
    fi

    # Parse with python (the only cross-platform way to do it safely).
    local up_to_date server_time_unix bundle_json
    up_to_date=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("up_to_date", False))' < "$STATE_DIR/last_response.json")
    server_time_unix=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("server_time_unix", 0))' < "$STATE_DIR/last_response.json")
    bundle_json=$(python3 -c '
import json, sys
d = json.load(sys.stdin)
b = d.get("bundle")
print(json.dumps(b) if b else "")
' < "$STATE_DIR/last_response.json")

    # Always advance the local pointer, even if up_to_date. The 60s
    # cadence means we don't want to keep re-fetching the same bundle.
    write_last_seen "$server_time_unix"

    if [ "$up_to_date" = "True" ] || [ -z "$bundle_json" ]; then
        echo "$LOG_PREFIX  ✓ up to date (since=$last_seen → $server_time_unix)"
        return 0
    fi

    # A new bundle is here — apply it.
    apply_bundle "$bundle_json"
}

# ─── Main loop ─────────────────────────────────────────────────────────────
echo "$LOG_PREFIX  relay=$RELAY_URL interval=${INTERVAL}s profile=$PROFILE_DIR"

if [ "$RUN_ONCE" = "1" ]; then
    poll_once
    exit $?
fi

while true; do
    if ! poll_once; then
        # Don't sleep a full interval on a transient error; nudge forward
        # and try again. The relay being down for a tick or two should
        # not delay the next legitimate update by a minute.
        sleep 5
        continue
    fi
    sleep "$INTERVAL"
done
