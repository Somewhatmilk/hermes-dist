#!/usr/bin/env bash
# dry-run.sh — builds the relay Docker image and runs the test suite
# against a local instance. Verifies HMAC, registration, event submission,
# and operator auth work end-to-end.

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

# 3. Run the container in the background
echo "→ Starting container..."
CONTAINER=$(docker run -d --rm \
    --name hermes-relay-test \
    -p 127.0.0.1:9119:9119 \
    -e OPERATOR_TOKEN="$OPERATOR_TOKEN" \
    -v "$(pwd)/test-data:/var/lib/hermes-relay" \
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

# 5. Run the test event script
echo
echo "→ Running test event script..."
bash tests/fire-test-event.sh

# 6. Cleanup
echo
echo "→ Cleaning up..."
docker stop "$CONTAINER" > /dev/null
echo "  ✓ Container stopped"

echo
echo "=== Dry-Run Complete ==="
echo "  All tests passed. The relay is ready to deploy."
