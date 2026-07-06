#!/usr/bin/env bash
# ~/.hermes/profiles/default-template/hooks/pre-tool.sh
#
# Shell-layer tool allowlist enforcement. Runs BEFORE every tool call.
# This is the single most important security boundary in the user install.
# It runs at the shell layer, NOT the config layer, because config-layer
# gates can be bypassed by a successful prompt-injection that rewrites
# config.yaml. The shell layer cannot be bypassed without write access
# to this file — which the user does not have.
#
# Environment provided by hermes (every tool call):
#   HERMES_TOOL_NAME        - e.g. "file:write_file", "browser:browser_navigate"
#   HERMES_TOOL_ARGS_JSON   - JSON object of the tool's arguments
#   HERMES_PROFILE          - the calling profile name
#   HERMES_USER_UUID        - this user's UUID
#   HERMES_HOME             - hermes home directory
#
# Exit codes:
#   0 = allow
#   1 = deny (this script prints the reason to stderr; hermes surfaces it)

set -euo pipefail

TOOL_NAME="${HERMES_TOOL_NAME:-}"
TOOL_ARGS="${HERMES_TOOL_ARGS_JSON:-{}}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE_DIR="$HERMES_HOME/profiles/default-template"
DENYLIST="$PROFILE_DIR/security/denylist.yaml"
ALLOWLIST="$PROFILE_DIR/security/allowlist.yaml"

# ─── Helper: extract a YAML list (block under a key) ──────────────────────
# Reads from stdin. Outputs one item per line, quotes + comments stripped.
extract_yaml_list() {
    local key="$1"
    awk -v k="^${key}:" '
        $0 ~ k { flag=1; next }
        /^[a-z_]+:/ { flag=0 }
        flag
    ' | sed -E 's/[[:space:]]*#.*$//' | sed -E 's/^[[:space:]]*-?[[:space:]]*//' | sed -E 's/^"//; s/"[[:space:]]*$//' | grep -v '^[[:space:]]*$'
}

# ─── 1. Tool must be in the allowlist ─────────────────────────────────────
TOOL_ALLOWED=0
while IFS= read -r allowed_tool; do
    if [ "$TOOL_NAME" = "$allowed_tool" ]; then
        TOOL_ALLOWED=1
        break
    fi
done < <(extract_yaml_list "tools" < "$ALLOWLIST")

if [ "$TOOL_ALLOWED" -eq 0 ]; then
    echo "BLOCKED: tool '$TOOL_NAME' is not in the allowlist." >&2
    echo "         This is the operator's security policy, not a bug." >&2
    exit 1
fi

# ─── 2. Path-scoped tools must target an allowed path root ────────────────
case "$TOOL_NAME" in
  file:write_file|file:patch|file:read_file|file:search_files)
    # Extract the path arg
    TARGET_PATH=$(echo "$TOOL_ARGS" | grep -oE '"(path|file_path|target)"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"[^"]+"\s*:\s*"([^"]+)".*/\1/')

    if [ -z "$TARGET_PATH" ]; then
      echo "BLOCKED: file tool called with no path argument." >&2
      exit 1
    fi

    # Expand ~ and resolve to absolute
    EXPANDED="${TARGET_PATH/#\~/$HOME}"

    # Check against denylist
    while IFS= read -r pattern; do
        if echo "$EXPANDED" | grep -qE "$pattern" 2>/dev/null; then
            echo "BLOCKED: path '$EXPANDED' matches denylist pattern: $pattern" >&2
            echo "         File tools cannot touch operator paths." >&2
            exit 1
        fi
    done < <(extract_yaml_list "paths" < "$DENYLIST")

    # Check against allowlist path roots
    ALLOWED=0
    while IFS= read -r root; do
        EXPANDED_ROOT="${root/#\~/$HOME}"
        if [[ "$EXPANDED" == "$EXPANDED_ROOT"* ]]; then
            ALLOWED=1
            break
        fi
    done < <(extract_yaml_list "path_roots" < "$ALLOWLIST")

    if [ "$ALLOWED" -eq 0 ]; then
      echo "BLOCKED: path '$EXPANDED' is not under any allowed path root." >&2
      echo "         Allowed roots: see $ALLOWLIST" >&2
      exit 1
    fi
    ;;

  browser:*|web:*|x_search:*)
    # URL denylist for outbound requests
    TARGET_URL=$(echo "$TOOL_ARGS" | grep -oE '"(url|target_url|uri)"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"[^"]+"\s*:\s*"([^"]+)".*/\1/')
    if [ -n "$TARGET_URL" ]; then
      while IFS= read -r pattern; do
        if echo "$TARGET_URL" | grep -qE "$pattern" 2>/dev/null; then
          echo "BLOCKED: URL '$TARGET_URL' matches denylist pattern: $pattern" >&2
          exit 1
        fi
      done < <(extract_yaml_list "urls" < "$DENYLIST")
    fi
    ;;
esac

# ─── 3. Audit log entries ─────────────────────────────────────────────────
mkdir -p "$HERMES_HOME"
AUDIT_LOG="$HERMES_HOME/audit.log"

if [ "$TOOL_NAME" = "memory:mnemosyne_remember" ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) MEMORY_SAVE profile=$HERMES_PROFILE uuid=$HERMES_USER_UUID args=$TOOL_ARGS" >> "$AUDIT_LOG"
fi

if [[ "$TOOL_NAME" == "skills:skill_manage" || "$TOOL_NAME" == "skills:*" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SKILL_MANAGE profile=$HERMES_PROFILE uuid=$HERMES_USER_UUID args=$TOOL_ARGS" >> "$AUDIT_LOG"
fi

# Allow
exit 0
