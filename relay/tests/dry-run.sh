#!/usr/bin/env bash
# dry-run.sh — builds the relay Docker image and runs the test suite
# against a local instance. Verifies HMAC, registration, event submission,
# operator auth, and T9 3-layer dedup end-to-end.

set -euo pipefail

RELAY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RELAY_DIR"

echo "=== Hermes Dist Relay — Dry-Run Test ==="
echo

# 1. Generate a random operator token
export OPERATOR_TOKEN=$(openssl rand -hex 32)
echo "Generated operator token: $OPERATOR_TOKEN"
echo "$OPERATOR_TOKEN" > .operator-token-test

# 2. Build the image
echo "→ Building Docker image..."
docker build -t hermes-relay:test .

# 3. Run the container in the background. RELAY_DISABLE_SCHEDULER=1 turns
# off the APScheduler retention job so it doesn't fire in the middle of
# the test.
#
# IMPORTANT: Use Windows-native path for the -v bind source. The POSIX
# form "$(pwd)/test-data:/var/lib/hermes-relay" silently triggers MSYS
# gotcha #3 (the `;C` corruption — MSYS sees the colon between source
# and dest as a Windows drive-letter separator and appends the current
# drive letter to the source). The container starts but the bind is
# empty. See `hermes-windows-filesystem-ops` skill
# references/docker-exec-msys.md section "THIRD gotcha" for the full
# diagnosis. cygpath -w converts POSIX to native on MSYS; on Mac/Linux
# it's a no-op passthrough.
echo "→ Starting container..."
# Use Windows-native path for the -v bind source on MSYS. The POSIX
# form "$(pwd)/test-data:/var/lib/hermes-relay" silently triggers
# MSYS gotcha #3 (the `;C` corruption — MSYS sees the colon between
# source and dest as a Windows drive-letter separator). cygpath -w
# converts POSIX to native on MSYS; on Mac/Linux it's a no-op
# passthrough. See `hermes-windows-filesystem-ops` skill
# references/docker-exec-msys.md section "THIRD gotcha" for the full
# diagnosis.
TEST_DATA_SRC="$(cygpath -w "$(pwd)/test-data" 2>/dev/null || echo "$(pwd)/test-data")"
CONTAINER=$(docker run -d --rm \
    --name hermes-relay-test \
    -p 127.0.0.1:9119:9119 \
    -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
    -e RELAY_DISABLE_SCHEDULER=1 \
    -v "$TEST_DATA_SRC:/var/lib/hermes-relay" \
    hermes-relay:test)
echo "  Container: $CONTAINER"

# 4. Wait for health
echo "→ Waiting for health check..."
for i in {1..30}; do
    if curl -sS http://127.0.0.1:9119/api/v1/healthz > /dev/null 2>&1; then
        echo "  ✓ Healthy after ${i}s"
        break
    fi
    sleep 1
done

# 5. Run the original single-event test (HMAC, replay, bad-sig)
echo
echo "→ Running single-event test..."
bash tests/fire-test-event.sh

# 6. Run the T9 3-layer dedup flood test (1000 identical events +
#    1000 tool_invocation events with same argv)
echo
echo "→ Running T9 dedup flood test (1000 identical events)..."
# T9: ensure a clean DB so the dedup assertions are exact. We do this
# by deleting the test-data/relay.db and restarting the container. If
# the DB has prior rows, MAX_ROWS_FOR_FLOOD = 10 would still pass for
# a single user, but the dedup_count assertion becomes ambiguous.
if [ -f test-data/relay.db ]; then
    echo "  → Removing stale test-data/relay.db for clean assertions..."
    rm -f test-data/relay.db test-data/relay.db-shm test-data/relay.db-wal
    docker stop "$CONTAINER" > /dev/null
    CONTAINER=$(docker run -d --rm \
        --name hermes-relay-test \
        -p 127.0.0.1:9119:9119 \
        -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
        -e RELAY_DISABLE_SCHEDULER=1 \
        -v "$TEST_DATA_SRC:/var/lib/hermes-relay" \
        hermes-relay:test)
    for i in {1..30}; do
        if curl -sS http://127.0.0.1:9119/api/v1/healthz > /dev/null 2>&1; then
            echo "  ✓ Restarted cleanly after ${i}s"
            break
        fi
        sleep 1
    done
fi
bash tests/flood-dedup-test.sh

# 6b. Run the T3 profile-bundle push test (operator publish + user fetch)
echo
echo "→ Running T3 profile-bundle push test..."
if [ -f test-data/relay.db ]; then
    rm -f test-data/relay.db test-data/relay.db-shm test-data/relay.db-wal
    docker stop "$CONTAINER" > /dev/null
    CONTAINER=$(docker run -d --rm \
        --name hermes-relay-test \
        -p 127.0.0.1:9119:9119 \
        -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
        -e RELAY_DISABLE_SCHEDULER=1 \
        -v "$TEST_DATA_SRC:/var/lib/hermes-relay" \
        hermes-relay:test)
    for i in {1..30}; do
        if curl -sS http://127.0.0.1:9119/api/v1/healthz > /dev/null 2>&1; then
            echo "  ✓ Restarted cleanly after ${i}s"
            break
        fi
        sleep 1
    done
fi
bash tests/profile-bundle-test.sh

# 7. Cleanup
echo
echo "→ Cleaning up..."
docker stop "$CONTAINER" > /dev/null
echo "  ✓ Container stopped"

echo
echo "=== Dry-Run Complete ==="
echo "  All tests passed. The relay is ready to deploy."
