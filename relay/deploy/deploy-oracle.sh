#!/usr/bin/env bash
# deploy-oracle.sh — deploys the relay to an Oracle Cloud Always Free ARM instance.
#
# Prerequisites (you do these manually):
#   1. Sign up at https://cloud.oracle.com/ (free, requires a credit card on file
#      but you won't be charged)
#   2. Create a "VM.Standard.A1.Flex" instance with shape 1 OCPU / 6 GB RAM
#      (or up to 4 OCPU / 24 GB — free tier allows it)
#   3. Use Oracle Linux 8 or Ubuntu 22.04 minimal image
#   4. Save the SSH private key (e.g. ~/oracle-key.pem)
#   5. Note the public IP of the instance
#   6. Open port 9119 in the VCN's security list (ingress, TCP, source 0.0.0.0/0)
#   7. Open port 22 (SSH) — usually open by default
#
# Usage:
#   ./deploy-oracle.sh ubuntu@<public-ip> -i ~/oracle-key.pem
#
# What it does:
#   - Installs Docker + docker compose on the instance
#   - Copies the relay/ directory to /opt/hermes-relay
#   - Generates a random OPERATOR_TOKEN
#   - Builds + starts the relay container
#   - Installs the systemd unit + daily-ping timer
#   - Prints the health check URL and operator token

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 user@host [-i keyfile]" >&2
    exit 1
fi

TARGET="$1"
KEYFILE="${2:-}"
[ -z "$KEYFILE" ] && KEYFILE_FLAG="" || KEYFILE_FLAG="-i $KEYFILE"

RELAY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Relay source: $RELAY_DIR"
echo "Target: $TARGET"

SSH="ssh $KEYFILE_FLAG -o StrictHostKeyChecking=accept-new $TARGET"
SCP="scp $KEYFILE_FLAG -o StrictHostKeyChecking=accept-new"

# 1. Test connectivity
echo "→ Testing SSH connectivity..."
$SSH "echo 'connected'" || { echo "SSH failed"; exit 1; }

# 2. Install Docker on the instance
echo "→ Installing Docker (this may take 1-2 minutes)..."
$SSH "
    if ! command -v docker >/dev/null 2>&1; then
        # Detect OS
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            case \"\$ID\" in
                ubuntu|debian)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq ca-certificates curl
                    sudo install -m 0755 -d /etc/apt/keyrings
                    sudo curl -fsSL https://download.docker.com/linux/\$ID/gpg -o /etc/apt/keyrings/docker.asc
                    sudo chmod a+r /etc/apt/keyrings/docker.asc
                    echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/\$ID \$(. /etc/os-release && echo \"\${VERSION_CODENAME}\") stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                    ;;
                ol|rhel|centos|fedora|rocky|almalinux)
                    sudo dnf install -y -q dnf-utils
                    sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
                    sudo dnf install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                    ;;
                *)
                    echo 'Unsupported OS: '\$ID; exit 1
                    ;;
            esac
        fi
        sudo systemctl enable --now docker
        sudo usermod -aG docker \$USER
    fi
    docker --version
    docker compose version
"

# 3. Copy the relay files
echo "→ Copying relay files..."
$SSH "sudo mkdir -p /opt/hermes-relay && sudo chown \$USER:\$USER /opt/hermes-relay"
$SCP -r "$RELAY_DIR/." "$TARGET:/opt/hermes-relay/"

# 4. Generate operator token
OPERATOR_TOKEN=$(openssl rand -hex 32)
echo "→ Generated operator token: $OPERATOR_TOKEN"

# 5. Set up environment + start
echo "→ Starting relay..."
$SSH "
    cd /opt/hermes-relay
    echo 'OPERATOR_TOKEN=$OPERATOR_TOKEN' > .env
    docker compose up -d --build
    sleep 5
    curl -sS http://127.0.0.1:9119/api/v1/healthz
"

# 6. Install systemd unit + daily ping
echo "→ Installing systemd service + daily ping timer..."
$SCP "$RELAY_DIR/deploy/relay.service" "$TARGET:/tmp/relay.service"
$SCP "$RELAY_DIR/deploy/relay-ping.timer" "$TARGET:/tmp/relay-ping.timer"
$SCP "$RELAY_DIR/deploy/daily-ping.sh" "$TARGET:/tmp/daily-ping.sh"
$SSH "
    sudo mv /tmp/relay.service /etc/systemd/system/
    sudo mv /tmp/relay-ping.timer /etc/systemd/system/
    sudo mv /tmp/daily-ping.sh /opt/hermes-relay/deploy/daily-ping.sh
    sudo chmod +x /opt/hermes-relay/deploy/daily-ping.sh
    sudo touch /var/log/hermes-relay-ping.log
    sudo systemctl daemon-reload
    sudo systemctl enable --now hermes-relay-ping.timer
    echo 'Service installed. Check status:'
    sudo systemctl status hermes-relay --no-pager || true
"

# 7. Final summary
PUBLIC_IP=$(echo "$TARGET" | cut -d@ -f2)
echo
echo "=== Deployment Complete ==="
echo "  Public URL:  http://$PUBLIC_IP:9119"
echo "  Health:      http://$PUBLIC_IP:9119/api/v1/healthz"
echo "  Operator:    OPERATOR_TOKEN=$OPERATOR_TOKEN"
echo
echo "Save the operator token in your password manager."
echo "Use it to query events: curl -H 'X-Operator-Token: \$TOKEN' http://$PUBLIC_IP:9119/api/v1/events"
