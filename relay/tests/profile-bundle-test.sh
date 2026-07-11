#!/usr/bin/env bash
# profile-bundle-test.sh — fires a profile-bundle push end-to-end.
# Verifies T3: operator publish + user-side fetch with HMAC + dedup.
#
# Required env (set by dry-run.sh):
#   RELAY_URL      default http://127.0.0.1:9119
#   OPERATOR_TOKEN the operator's 64-hex-char token
#
# Steps:
#   1. Register a user (gets hmac_secret for downstream signing).
#   2. POST /api/v1/profile-bundle (operator auth) — first publish.
#   3. Re-POST same version — assert inserted=false.
#   4. Build a signed GET /api/v1/profile-bundle?since=0 — assert bundle.
#   5. GET with since=future — assert up_to_date=true.
#   6. GET with bad signature — assert 401.
#   7. GET with signature for since=0 but URL ?since=9999999 — assert 401
#      (catches the canonical-replay-attack that GET canonical is designed
#       to prevent).

set -euo pipefail

RELAY_URL="${RELAY_URL:-http://127.0.0.1:9119}"
OP_TOKEN="${OPERATOR_TOKEN:-}"
if [ -z "$OP_TOKEN" ] && [ -f .operator-token-test ]; then
    OP_TOKEN=$(cat .operator-token-test)
fi
if [ -z "$OP_TOKEN" ]; then
    echo "✗ OPERATOR_TOKEN not set and .operator-token-test missing" >&2
    exit 1
fi

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

# Python helpers (HMAC + JSON assembly — bash can't do this safely)
py_hmac_post() {
    # Args: $1=uuid  $2=secret  $3=timestamp  $4=nonce  $5=event_type  $6=body
    python3 - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import base64, hashlib, hmac, sys
u, s, ts, nonce, et, body = sys.argv[1:7]
canonical = "\n".join([u, ts, nonce, et, body])
sig = base64.b64encode(
    hmac.new(s.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
).decode("ascii")
print(sig)
PY
}

py_hmac_get() {
    # Args: $1=uuid  $2=secret  $3=timestamp  $4=nonce  $5=event_type  $6=method+path+query
    python3 - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import base64, hashlib, hmac, sys
u, s, ts, nonce, et, canonical_field = sys.argv[1:7]
canonical = "\n".join([u, ts, nonce, et, canonical_field])
sig = base64.b64encode(
    hmac.new(s.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
).decode("ascii")
print(sig)
PY
}

py_uuid() { python3 -c 'import uuid; print(str(uuid.uuid4()))'; }

echo "=== T3 Profile Bundle Push Test ==="
echo "    relay: $RELAY_URL"
echo

# 1. Register a user
TEST_UUID=$(py_uuid)
REG_BODY=$(cat <<EOF
{
  "uuid": "$TEST_UUID",
  "os": "t3-test-runner",
  "version": "hermes-dist-t3-test",
  "opted_in": true,
  "registered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
echo "→ Registering test user $TEST_UUID..."
REG_RESP=$(curl -sS -X POST "$RELAY_URL/api/v1/register" \
    -H "Content-Type: application/json" \
    -d "$REG_BODY")
TEST_SECRET=$(echo "$REG_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("hmac_secret",""))')
if [ -z "$TEST_SECRET" ]; then
    red "  ✗ register did not return hmac_secret"
    exit 1
fi
echo "  ✓ registered, secret acquired (${#TEST_SECRET} chars)"

# 2. POST /api/v1/profile-bundle (operator auth) — first publish
VERSION="v0.2.0-t3-dryrun-$(date +%s)"
RELEASED_AT="2026-07-11T13:00:00Z"
PUBLISH_BODY=$(cat <<EOF
{
  "soul_md": "# Operator SOUL\nTest bundle from dry-run.sh",
  "config_yaml": "toolsets:\n  - file\n  - web\n",
  "toolsets_json": "[\"file\",\"web\",\"docker\",\"webscraping\"]",
  "version": "$VERSION",
  "released_at": "$RELEASED_AT"
}
EOF
)
echo "→ Publishing profile bundle (operator auth) version=$VERSION..."
HTTP_CODE=$(curl -sS -o /tmp/t3-publish-1.json -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/profile-bundle" \
    -H "Content-Type: application/json" \
    -H "X-Operator-Token: $OP_TOKEN" \
    -d "$PUBLISH_BODY" \
    --max-time 10)
if [ "$HTTP_CODE" != "200" ]; then
    red "  ✗ publish returned HTTP $HTTP_CODE"
    cat /tmp/t3-publish-1.json
    exit 1
fi
INSERTED_1=$(python3 -c 'import json; print(json.load(open("/tmp/t3-publish-1.json")).get("inserted"))')
if [ "$INSERTED_1" != "True" ]; then
    red "  ✗ first publish should have inserted=true (got $INSERTED_1)"
    exit 1
fi
green "  ✓ first publish inserted=true"

# 3. Re-POST same version — assert inserted=false (dedup)
HTTP_CODE=$(curl -sS -o /tmp/t3-publish-2.json -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/profile-bundle" \
    -H "Content-Type: application/json" \
    -H "X-Operator-Token: $OP_TOKEN" \
    -d "$PUBLISH_BODY" \
    --max-time 10)
INSERTED_2=$(python3 -c 'import json; print(json.load(open("/tmp/t3-publish-2.json")).get("inserted"))')
if [ "$INSERTED_2" != "False" ]; then
    red "  ✗ republish same version should have inserted=false (got $INSERTED_2)"
    exit 1
fi
green "  ✓ republish dedup (inserted=false)"

# 4. Build a signed GET /api/v1/profile-bundle?since=0 — assert bundle
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(py_uuid)
GET_PATH_QS="/api/v1/profile-bundle?since=0"
GET_CANONICAL_FIELD="GET $GET_PATH_QS"
SIG=$(py_hmac_get "$TEST_UUID" "$TEST_SECRET" "$TS" "$NONCE" "profile_bundle" "$GET_CANONICAL_FIELD")
HTTP_CODE=$(curl -sS -o /tmp/t3-fetch-1.json -w "%{http_code}" \
    -X GET "$RELAY_URL$GET_PATH_QS" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TS" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: $SIG" \
    -H "X-Hermes-Event-Type: profile_bundle" \
    --max-time 10)
if [ "$HTTP_CODE" != "200" ]; then
    red "  ✗ GET returned HTTP $HTTP_CODE"
    cat /tmp/t3-fetch-1.json
    exit 1
fi
UP_TO_DATE=$(python3 -c 'import json; print(json.load(open("/tmp/t3-fetch-1.json")).get("up_to_date"))')
GOT_VERSION=$(python3 -c 'import json; d=json.load(open("/tmp/t3-fetch-1.json")); print(d.get("bundle",{}).get("version",""))')
if [ "$UP_TO_DATE" != "False" ] || [ "$GOT_VERSION" != "$VERSION" ]; then
    red "  ✗ GET should return up_to_date=false + bundle.version=$VERSION (got up_to_date=$UP_TO_DATE, version=$GOT_VERSION)"
    exit 1
fi
green "  ✓ GET since=0 returned the bundle"

# 5. GET with since=future — assert up_to_date=true
SERVER_NOW=$(python3 -c 'import json; print(json.load(open("/tmp/t3-fetch-1.json")).get("server_time_unix"))')
FUTURE=$((SERVER_NOW + 1000000))
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(py_uuid)
GET_PATH_QS="/api/v1/profile-bundle?since=$FUTURE"
SIG=$(py_hmac_get "$TEST_UUID" "$TEST_SECRET" "$TS" "$NONCE" "profile_bundle" "GET $GET_PATH_QS")
HTTP_CODE=$(curl -sS -o /tmp/t3-fetch-2.json -w "%{http_code}" \
    -X GET "$RELAY_URL$GET_PATH_QS" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TS" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: $SIG" \
    -H "X-Hermes-Event-Type: profile_bundle" \
    --max-time 10)
UP_TO_DATE=$(python3 -c 'import json; print(json.load(open("/tmp/t3-fetch-2.json")).get("up_to_date"))')
if [ "$HTTP_CODE" != "200" ] || [ "$UP_TO_DATE" != "True" ]; then
    red "  ✗ GET since=future should return up_to_date=true (got http=$HTTP_CODE, up_to_date=$UP_TO_DATE)"
    exit 1
fi
green "  ✓ GET since=future returned up_to_date=true"

# 6. GET with bad signature — assert 401
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(py_uuid)
HTTP_CODE=$(curl -sS -o /tmp/t3-fetch-3.json -w "%{http_code}" \
    -X GET "$RELAY_URL/api/v1/profile-bundle?since=0" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TS" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=" \
    -H "X-Hermes-Event-Type: profile_bundle" \
    --max-time 10)
if [ "$HTTP_CODE" != "401" ]; then
    red "  ✗ GET with bad signature should return 401 (got $HTTP_CODE)"
    exit 1
fi
green "  ✓ GET with bad signature rejected (401)"

# 7. Replay-attack guard: sign for since=0, send as since=9999999999
#    (GET canonical signs METHOD+path+query, so this should 401)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(py_uuid)
SIG_FOR_0=$(py_hmac_get "$TEST_UUID" "$TEST_SECRET" "$TS" "$NONCE" "profile_bundle" "GET /api/v1/profile-bundle?since=0")
HTTP_CODE=$(curl -sS -o /tmp/t3-fetch-4.json -w "%{http_code}" \
    -X GET "$RELAY_URL/api/v1/profile-bundle?since=9999999999" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TS" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: $SIG_FOR_0" \
    -H "X-Hermes-Event-Type: profile_bundle" \
    --max-time 10)
if [ "$HTTP_CODE" != "401" ]; then
    red "  ✗ signature for since=0 replayed as since=9999999999 should 401 (got $HTTP_CODE)"
    exit 1
fi
green "  ✓ replay attack (signed since=0, sent since=9999999999) rejected (401)"

echo
echo "=== T3 Profile Bundle Push Test: PASS ==="
echo "  - operator publish (inserted=true on first, =false on dedup)"
echo "  - user-side fetch with HMAC + GET-canonical (since=0 returns bundle)"
echo "  - user-side fetch up_to_date=true when since > latest"
echo "  - bad signature rejected (401)"
echo "  - signature-for-since=0 cannot be replayed as since=future (401)"
echo
echo "=== All T3 test cases passed ==="