#!/usr/bin/env bash
# hermes-distribution — operator-side CLI for the hermes-dist PoC.
# Wraps the most common operator actions: pull events, list users,
# review quarantined items.

set -euo pipefail

COLLECTOR_DIR="$HOME/.hermes/profiles/collector"
QUARANTINE="$COLLECTOR_DIR/quarantine"

print_help() {
    cat <<EOF
hermes-distribution — operator CLI for hermes-dist PoC

Usage:
    hermes-distribution pull                 Pull pending events from relay
    hermes-distribution list                 List quarantined items
    hermes-distribution review <type>        Review items of a type (skills, scripts, memories)
    hermes-distribution approve <file>       Approve an item (move to approved/)
    hermes-distribution reject <file> <reason>  Reject an item with reason
    hermes-distribution health               Check relay health
    hermes-distribution help                 This message

Examples:
    hermes-distribution pull
    hermes-distribution list
    hermes-distribution review scripts
    hermes-distribution approve quarantine/scripts/clean/foo.json
EOF
}

cmd_pull() {
    bash "$COLLECTOR_DIR/pull-relay.sh"
}

cmd_list() {
    echo "=== Quarantined items ==="
    echo
    for dir in "$QUARANTINE"/skills/clean "$QUARANTINE"/skills/flagged "$QUARANTINE"/scripts "$QUARANTINE"/memories; do
        if [ -d "$dir" ]; then
            count=$(ls -1 "$dir" 2>/dev/null | wc -l)
            if [ "$count" -gt 0 ]; then
                rel="${dir#$QUARANTINE/}"
                echo "[$rel] ($count items)"
                ls -lah "$dir" | tail -n +2 | head -n 10
                echo
            fi
        fi
    done
}

cmd_review() {
    local type="${1:-}"
    case "$type" in
        skills)
            DIR="$QUARANTINE/skills/clean"
            ;;
        scripts)
            DIR="$QUARANTINE/scripts"
            ;;
        memories)
            DIR="$QUARANTINE/memories"
            ;;
        *)
            echo "Usage: hermes-distribution review <skills|scripts|memories>"
            exit 1
            ;;
    esac

    echo "=== Reviewing $type in $DIR ==="
    for f in "$DIR"/*.json; do
        [ -f "$f" ] || continue
        echo
        echo "--- $(basename "$f") ---"
        python3 -c "
import json
with open('$f', 'r', encoding='utf-8') as fp:
    data = json.load(fp)
print(f'  UUID: {data[\"user_uuid\"]}')
print(f'  Type: {data[\"event_type\"]}')
print(f'  Received: {data[\"received_at\"]}')
print(f'  Size: {data[\"payload_size\"]} bytes')
print(f'  Sig valid: {data[\"signature_valid\"]}')
print(f'  Payload preview:')
print(data.get('raw_payload', '')[:500])
"
    done
}

cmd_approve() {
    local file="${1:-}"
    if [ -z "$file" ] || [ ! -f "$file" ]; then
        echo "Usage: hermes-distribution approve <file>"
        exit 1
    fi
    local dest="$QUARANTINE/approved/$(basename "$file")"
    mkdir -p "$QUARANTINE/approved"
    mv "$file" "$dest"
    echo "APPROVED: $file → $dest" >> "$COLLECTOR_DIR/audit/audit.log"
    echo "✓ Approved: $(basename "$file")"
}

cmd_reject() {
    local file="${1:-}"
    local reason="${2:-no reason given}"
    if [ -z "$file" ] || [ ! -f "$file" ]; then
        echo "Usage: hermes-distribution reject <file> <reason>"
        exit 1
    fi
    local dest="$QUARANTINE/rejected/$(basename "$file")"
    mkdir -p "$QUARANTINE/rejected"
    mv "$file" "$dest"
    echo "REJECTED: $file reason=\"$reason\"" >> "$COLLECTOR_DIR/audit/audit.log"
    echo "✗ Rejected: $(basename "$file") — $reason"
}

cmd_health() {
    local config="$COLLECTOR_DIR/config.yaml"
    local url=$(grep -E '^\s*url:' "$config" | head -1 | sed -E 's/.*url:\s*"?([^"]+)"?.*/\1/' | tr -d '"')
    echo "Relay: $url"
    curl -sS "$url/api/v1/healthz" | python3 -m json.tool
}

case "${1:-help}" in
    pull) cmd_pull ;;
    list) cmd_list ;;
    review) shift; cmd_review "$@" ;;
    approve) shift; cmd_approve "$@" ;;
    reject) shift; cmd_reject "$@" ;;
    health) cmd_health ;;
    help|*) print_help ;;
esac
