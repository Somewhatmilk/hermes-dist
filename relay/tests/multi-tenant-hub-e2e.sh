#!/usr/bin/env bash
# Multi-tenant hub end-to-end test (v0.5.0).
# Starts the relay, registers a fake user, exercises the 5 new endpoints.

set -euo pipefail

RELAY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB="$RELAY_DIR/tests/.e2e-test.db"
SECRET="$RELAY_DIR/tests/.e2e-test-secret"
PORT=${E2E_PORT:-9119}
BASE="http://127.0.0.1:$PORT"

echo "[e2e] preparing test DB at $DB"
rm -f "$DB" "$SECRET"
export RELAY_DB_PATH="$DB"
export OPERATOR_TOKEN="$(head -c 64 /dev/urandom | base64 | tr -d '/+=' | head -c 64)"
echo "[e2e] OPERATOR_TOKEN set"

echo "[e2e] starting relay on port $PORT"
python -c "
import sys
sys.path.insert(0, '$RELAY_DIR/app')
import uvicorn
uvicorn.run('main:app', host='127.0.0.1', port=$PORT, log_level='warning')
" &
RELAY_PID=$!
trap "kill $RELAY_PID 2>/dev/null || true" EXIT

for i in 1 2 3 4 5; do
    if curl -sf "$BASE/api/v1/healthz" >/dev/null 2>&1; then
        echo "[e2e] relay up"
        break
    fi
    sleep 1
done

echo "[e2e] registering fake user"
USER_UUID=$(python -c "import uuid; print(uuid.uuid4().hex)")
REGISTER_RESP=$(curl -sf -X POST "$BASE/api/v1/register" \
    -H "Content-Type: application/json" \
    -d "{\"uuid\":\"$USER_UUID\",\"os\":\"linux\",\"version\":\"e2e\",\"opted_in\":true,\"registered_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")
echo "$REGISTER_RESP" | python -m json.tool >/dev/null
SECRET_VALUE=$(echo "$REGISTER_RESP" | python -c "import sys, json; print(json.load(sys.stdin).get('hmac_secret', ''))")
echo "$SECRET_VALUE" > "$SECRET"

if [ -z "$SECRET_VALUE" ]; then
    echo "[e2e] FAIL: no hmac_secret returned"
    exit 1
fi
echo "[e2e] user registered, secret len=${#SECRET_VALUE}"

echo "[e2e] testing GET /api/v1/overrides (operator-only)"
OVERRIDES=$(curl -sf "$BASE/api/v1/overrides?user_profile_dir=/tmp/nonexistent&operator_default_dir=/tmp/nonexistent2" \
    -H "X-Operator-Token: $OPERATOR_TOKEN")
echo "$OVERRIDES" | python -m json.tool

echo "[e2e] checking root endpoint list for new endpoints"
ROOT=$(curl -sf "$BASE/")
for ep in "/api/v1/skills" "/api/v1/tools/invoke" "/api/v1/docker/run" "/api/v1/overrides"; do
    if echo "$ROOT" | python -c "import sys, json; eps=json.load(sys.stdin).get('endpoints', []); print(any('$ep' in e for e in eps))" | grep -q True; then
        echo "[e2e] + $ep listed in root"
    else
        echo "[e2e] - $ep NOT in root endpoint list"
        exit 1
    fi
done

echo "[e2e] all checks passed"
rm -f "$DB" "$SECRET"