#!/usr/bin/env bash
# fire-test-event.sh — fires a single signed test event at a running relay.
# Used by dry-run.sh and by humans to verify the relay is accepting events.

set -euo pipefail

RELAY_URL="${RELAY_URL:-http://127.0.0.1:9119}"
TEST_UUID="${TEST_UUID:-$(python3 -c 'import uuid; print(str(uuid.uuid4()))')}"
TEST_SECRET="${TEST_SECRET:-$(openssl rand -hex 32)}"

# 1. Register
echo "→ Registering test user $TEST_UUID..."
REGISTER_BODY=$(cat <<EOF
{
  "uuid": "$TEST_UUID",
  "os": "test-runner",
  "version": "hermes-dist-poc-test",
  "opted_in": true,
  "registered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)

REGISTER_RESP=$(curl -sS -X POST "$RELAY_URL/api/v1/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_BODY")
echo "  Response: $REGISTER_RESP"

# If the relay returned a secret (first registration), use it
RETURNED_SECRET=$(echo "$REGISTER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("hmac_secret",""))')
if [ -n "$RETURNED_SECRET" ]; then
    TEST_SECRET="$RETURNED_SECRET"
fi

# 2. Build a signed payload
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NONCE=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
EVENT_TYPE="test_event"
BODY=$(cat <<EOF
{
  "test": true,
  "uuid": "$TEST_UUID",
  "message": "Hello from hermes-dist dry-run",
  "ts": "$TIMESTAMP"
}
EOF
)

CANONICAL=$(printf '%s\n%s\n%s\n%s\n%s' "$TEST_UUID" "$TIMESTAMP" "$NONCE" "$EVENT_TYPE" "$BODY")
SIGNATURE=$(printf '%s' "$CANONICAL" | openssl dgst -sha256 -hmac "$TEST_SECRET" -binary | base64 -w 0)

# 3. Submit
echo "→ Submitting signed test event..."
HTTP_CODE=$(curl -sS -o /tmp/relay-submit-response.txt -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/submit" \
    -H "Content-Type: application/json" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TIMESTAMP" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: $SIGNATURE" \
    -H "X-Hermes-Event-Type: $EVENT_TYPE" \
    -d "$BODY" \
    --max-time 10)

echo "  HTTP $HTTP_CODE"
cat /tmp/relay-submit-response.txt
echo

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ Event accepted"
else
    echo "  ✗ Event rejected"
    exit 1
fi

# 4. Try replay (same nonce)
echo "→ Replaying same nonce (should be rejected)..."
HTTP_CODE=$(curl -sS -o /tmp/relay-replay-response.txt -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/submit" \
    -H "Content-Type: application/json" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $TIMESTAMP" \
    -H "X-Hermes-Nonce: $NONCE" \
    -H "X-Hermes-Signature: $SIGNATURE" \
    -H "X-Hermes-Event-Type: $EVENT_TYPE" \
    -d "$BODY" \
    --max-time 10)

echo "  HTTP $HTTP_CODE (expected 401)"
if [ "$HTTP_CODE" = "401" ]; then
    echo "  ✓ Replay rejected"
else
    echo "  ✗ Replay NOT rejected (security issue!)"
    exit 1
fi

# 5. Try bad signature
echo "→ Submitting with bad signature (should be rejected)..."
BAD_SIG="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
HTTP_CODE=$(curl -sS -o /tmp/relay-bad-response.txt -w "%{http_code}" \
    -X POST "$RELAY_URL/api/v1/submit" \
    -H "Content-Type: application/json" \
    -H "X-Hermes-User: $TEST_UUID" \
    -H "X-Hermes-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -H "X-Hermes-Nonce: $(python3 -c 'import uuid; print(str(uuid.uuid4()))')" \
    -H "X-Hermes-Signature: $BAD_SIG" \
    -H "X-Hermes-Event-Type: $EVENT_TYPE" \
    -d "$BODY" \
    --max-time 10)

echo "  HTTP $HTTP_CODE (expected 401)"
if [ "$HTTP_CODE" = "401" ]; then
    echo "  ✓ Bad signature rejected"
else
    echo "  ✗ Bad signature NOT rejected (security issue!)"
    exit 1
fi

# 6. Operator query
if [ -f .operator-token-test ]; then
    OP_TOKEN=$(cat .operator-token-test)
    echo "→ Querying events as operator..."
    curl -sS -H "X-Operator-Token: $OP_TOKEN" "$RELAY_URL/api/v1/events" | python3 -m json.tool
fi

echo
echo "=== All test cases passed ==="
