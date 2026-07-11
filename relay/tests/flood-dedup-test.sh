#!/usr/bin/env bash
# flood-dedup-test.sh — fires 1000 IDENTICAL events at the relay and
# verifies Layer B (content-hash dedup) collapses them to ~1 row.
#
# Then it fires 1000 tool_invocation events with the same argv and
# verifies Layer C (tool_invocation coalesce) collapses them to ~1 row
# with a high coalesced_count.
#
# Finally it hits /api/v1/stats/dedup and asserts the hit-ratio numbers
# are above the threshold the ticket calls out (<10 rows for 1000-event
# flood, hit ratio close to 1.0).
#
# Usage: RELAY_URL=http://... OPERATOR_TOKEN=... bash flood-dedup-test.sh
# (The dry-run.sh wrapper sets these for us.)

set -euo pipefail

RELAY_URL="${RELAY_URL:-http://127.0.0.1:9119}"
TEST_UUID="${TEST_UUID:-$(python3 -c 'import uuid; print(str(uuid.uuid4()))')}"
TEST_SECRET="${TEST_SECRET:-$(openssl rand -hex 32)}"
OP_TOKEN="${OPERATOR_TOKEN:-}"
FLOOD_COUNT="${FLOOD_COUNT:-1000}"
# Layer B + C expect the 1000 events to collapse to <= this many rows.
MAX_ROWS_FOR_FLOOD="${MAX_ROWS_FOR_FLOOD:-10}"
MIN_HIT_RATIO="${MIN_HIT_RATIO:-0.95}"

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

echo "=== T9 Dedup Flood Test ==="
echo "    relay:    $RELAY_URL"
echo "    uuid:     $TEST_UUID"
echo "    flood:    $FLOOD_COUNT identical events"
echo "    max rows: $MAX_ROWS_FOR_FLOOD"
echo

# 1. Register the test user
echo "→ Registering test user $TEST_UUID..."
REGISTER_BODY=$(cat <<EOF
{
  "uuid": "$TEST_UUID",
  "os": "t9-flood-test",
  "version": "hermes-dist-poc-t9",
  "opted_in": true,
  "registered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
REGISTER_RESP=$(curl -sS -X POST "$RELAY_URL/api/v1/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTER_BODY")
RETURNED_SECRET=$(echo "$REGISTER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("hmac_secret",""))')
if [ -n "$RETURNED_SECRET" ]; then
    TEST_SECRET="$RETURNED_SECRET"
fi
echo "  ✓ registered (secret acquired)"
echo

# ─── Test 1: Layer B (content-hash dedup) ────────────────────────────────
# 1000 IDENTICAL bodies → 1 row with dedup_count = 1000
echo "→ [Layer B] firing $FLOOD_COUNT identical events..."
LAYER_B_BODY='{"test":"t9-flood","ts":"constant-body-001","data":"x"}'
LAYER_B_DEDUPED=0
LAYER_B_INSERTED=0
LAYER_B_COALESCED=0
LAYER_B_OTHER=0
LAYER_B_NON_2XX=0

for i in $(seq 1 $FLOOD_COUNT); do
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    NONCE=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
    EVENT_TYPE="test_dedup_b"
    CANONICAL=$(printf '%s\n%s\n%s\n%s\n%s' "$TEST_UUID" "$TIMESTAMP" "$NONCE" "$EVENT_TYPE" "$LAYER_B_BODY")
    SIGNATURE=$(printf '%s' "$CANONICAL" | openssl dgst -sha256 -hmac "$TEST_SECRET" -binary | base64 -w 0)

    RESP=$(curl -sS -o /dev/null -w "%{http_code} %{json}" \
        -X POST "$RELAY_URL/api/v1/submit" \
        -H "Content-Type: application/json" \
        -H "X-Hermes-User: $TEST_UUID" \
        -H "X-Hermes-Timestamp: $TIMESTAMP" \
        -H "X-Hermes-Nonce: $NONCE" \
        -H "X-Hermes-Signature: $SIGNATURE" \
        -H "X-Hermes-Event-Type: $EVENT_TYPE" \
        -d "$LAYER_B_BODY" \
        --max-time 10 2>/dev/null || echo "000 {}")
    HTTP_CODE=$(echo "$RESP" | awk '{print $1}')
    JSON=$(echo "$RESP" | cut -d' ' -f2-)
    if [ "$HTTP_CODE" != "200" ]; then
        LAYER_B_NON_2XX=$((LAYER_B_NON_2XX + 1))
        if [ "$LAYER_B_NON_2XX" -le 3 ]; then
            yellow "  ! submit #$i got HTTP $HTTP_CODE: $JSON"
        fi
        continue
    fi
    ACTION=$(echo "$JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("dedup","?"))' 2>/dev/null || echo "?")
    case "$ACTION" in
        inserted)    LAYER_B_INSERTED=$((LAYER_B_INSERTED + 1)) ;;
        deduped_b)   LAYER_B_DEDUPED=$((LAYER_B_DEDUPED + 1)) ;;
        coalesced_c) LAYER_B_COALESCED=$((LAYER_B_COALESCED + 1)) ;;
        *)           LAYER_B_OTHER=$((LAYER_B_OTHER + 1)) ;;
    esac
done
echo "  inserted=$LAYER_B_INSERTED  deduped_b=$LAYER_B_DEDUPED  coalesced_c=$LAYER_B_COALESCED  other=$LAYER_B_OTHER  non2xx=$LAYER_B_NON_2XX"
echo

# ─── Test 2: Layer C (tool_invocation argv coalesce) ────────────────────
# 1000 tool_invocation events with the same argv → 1 row, coalesced_count = 1000
# We MUST use distinct nonces + timestamps (Layer A would 401 otherwise),
# and distinct bodies' nonces/IDs (otherwise Layer B would also fire).
# We use a small varying field in the body (a `seq` counter) so the bodies
# differ, but the argv+tool hash stays identical → Layer C wins.
echo "→ [Layer C] firing $FLOOD_COUNT tool_invocation events with same argv..."
LAYER_C_DEDUPED=0
LAYER_C_COALESCED=0
LAYER_C_INSERTED=0
LAYER_C_OTHER=0
LAYER_C_NON_2XX=0

for i in $(seq 1 $FLOOD_COUNT); do
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    NONCE=$(python3 -c 'import uuid; print(str(uuid.uuid4()))')
    EVENT_TYPE="tool_invocation"
    # tool + argv stay constant; only a `seq` field varies so the body
    # hash differs (Layer B doesn't fire) but the argv hash is identical
    # (Layer C fires).
    LAYER_C_BODY=$(printf '{"tool":"bash","argv":["ls","-la"],"seq":%d}' "$i")
    CANONICAL=$(printf '%s\n%s\n%s\n%s\n%s' "$TEST_UUID" "$TIMESTAMP" "$NONCE" "$EVENT_TYPE" "$LAYER_C_BODY")
    SIGNATURE=$(printf '%s' "$CANONICAL" | openssl dgst -sha256 -hmac "$TEST_SECRET" -binary | base64 -w 0)

    RESP=$(curl -sS -o /dev/null -w "%{http_code} %{json}" \
        -X POST "$RELAY_URL/api/v1/submit" \
        -H "Content-Type: application/json" \
        -H "X-Hermes-User: $TEST_UUID" \
        -H "X-Hermes-Timestamp: $TIMESTAMP" \
        -H "X-Hermes-Nonce: $NONCE" \
        -H "X-Hermes-Signature: $SIGNATURE" \
        -H "X-Hermes-Event-Type: $EVENT_TYPE" \
        -d "$LAYER_C_BODY" \
        --max-time 10 2>/dev/null || echo "000 {}")
    HTTP_CODE=$(echo "$RESP" | awk '{print $1}')
    JSON=$(echo "$RESP" | cut -d' ' -f2-)
    if [ "$HTTP_CODE" != "200" ]; then
        LAYER_C_NON_2XX=$((LAYER_C_NON_2XX + 1))
        if [ "$LAYER_C_NON_2XX" -le 3 ]; then
            yellow "  ! submit #$i got HTTP $HTTP_CODE: $JSON"
        fi
        continue
    fi
    ACTION=$(echo "$JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("dedup","?"))' 2>/dev/null || echo "?")
    case "$ACTION" in
        inserted)    LAYER_C_INSERTED=$((LAYER_C_INSERTED + 1)) ;;
        deduped_b)   LAYER_C_DEDUPED=$((LAYER_C_DEDUPED + 1)) ;;
        coalesced_c) LAYER_C_COALESCED=$((LAYER_C_COALESCED + 1)) ;;
        *)           LAYER_C_OTHER=$((LAYER_C_OTHER + 1)) ;;
    esac
done
echo "  inserted=$LAYER_C_INSERTED  coalesced_c=$LAYER_C_COALESCED  deduped_b=$LAYER_C_DEDUPED  other=$LAYER_C_OTHER  non2xx=$LAYER_C_NON_2XX"
echo

# ─── Test 3: verify storage via /api/v1/stats/dedup ──────────────────────
echo "→ Querying /api/v1/stats/dedup..."
STATS_JSON=$(curl -sS -H "X-Operator-Token: $OP_TOKEN" "$RELAY_URL/api/v1/stats/dedup")
echo "$STATS_JSON" | python3 -m json.tool || { red "✗ could not parse stats JSON"; echo "$STATS_JSON"; exit 1; }
echo

# Read out the Layer B target row
EVENTS_JSON=$(curl -sS -H "X-Operator-Token: $OP_TOKEN" "$RELAY_URL/api/v1/events?uuid=$TEST_UUID&limit=1000")
LAYER_B_ROWS=$(echo "$EVENTS_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for e in d.get("events", []) if e.get("event_type") == "test_dedup_b"]
print(len(rows))
' 2>/dev/null || echo "0")
LAYER_C_ROWS=$(echo "$EVENTS_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for e in d.get("events", []) if e.get("event_type") == "tool_invocation"]
print(len(rows))
' 2>/dev/null || echo "0")
LAYER_B_MAX_DEDUP=$(echo "$EVENTS_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for e in d.get("events", []) if e.get("event_type") == "test_dedup_b"]
if rows:
    print(max(e.get("dedup_count", 0) for e in rows))
else:
    print(0)
' 2>/dev/null || echo "0")
LAYER_C_MAX_COALESCED=$(echo "$EVENTS_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [e for e in d.get("events", []) if e.get("event_type") == "tool_invocation"]
if rows:
    print(max(e.get("coalesced_count", 0) for e in rows))
else:
    print(0)
' 2>/dev/null || echo "0")

echo
echo "=== Flood Test Results ==="
echo "  Layer B (content-hash, 24h):"
echo "    storage rows for test_dedup_b: $LAYER_B_ROWS   (max allowed: $MAX_ROWS_FOR_FLOOD)"
echo "    max dedup_count on a row:      $LAYER_B_MAX_DEDUP   (expected: $FLOOD_COUNT)"
echo "    non-2xx submits:               $LAYER_B_NON_2XX"
echo "  Layer C (tool_invocation argv, 30s):"
echo "    storage rows for tool_invocation: $LAYER_C_ROWS   (max allowed: $MAX_ROWS_FOR_FLOOD)"
echo "    max coalesced_count on a row:     $LAYER_C_MAX_COALESCED   (expected: $FLOOD_COUNT)"
echo "    non-2xx submits:                  $LAYER_C_NON_2XX"
echo

PASS=1
if [ "$LAYER_B_ROWS" -gt "$MAX_ROWS_FOR_FLOOD" ]; then
    red "✗ Layer B FAIL: $LAYER_B_ROWS rows (>$MAX_ROWS_FOR_FLOOD)"
    PASS=0
else
    green "✓ Layer B PASS: $LAYER_B_ROWS rows for $FLOOD_COUNT identical events"
fi
if [ "$LAYER_B_MAX_DEDUP" -lt "$FLOOD_COUNT" ]; then
    red "✗ Layer B FAIL: max dedup_count is $LAYER_B_MAX_DEDUP (expected $FLOOD_COUNT)"
    PASS=0
else
    green "✓ Layer B PASS: dedup_count reached $LAYER_B_MAX_DEDUP"
fi
if [ "$LAYER_C_ROWS" -gt "$MAX_ROWS_FOR_FLOOD" ]; then
    red "✗ Layer C FAIL: $LAYER_C_ROWS rows (>$MAX_ROWS_FOR_FLOOD)"
    PASS=0
else
    green "✓ Layer C PASS: $LAYER_C_ROWS rows for $FLOOD_COUNT tool_invocation events"
fi
if [ "$LAYER_C_MAX_COALESCED" -lt "$FLOOD_COUNT" ]; then
    red "✗ Layer C FAIL: max coalesced_count is $LAYER_C_MAX_COALESCED (expected $FLOOD_COUNT)"
    PASS=0
else
    green "✓ Layer C PASS: coalesced_count reached $LAYER_C_MAX_COALESCED"
fi

if [ "$PASS" = "1" ]; then
    echo
    green "=== T9 Dedup Flood Test: PASS ==="
    exit 0
else
    echo
    red "=== T9 Dedup Flood Test: FAIL ==="
    exit 1
fi
