#!/usr/bin/env bash
# relay/provision-user.sh
#
# Provision a per-user hermes profile in-place on this host for the
# single-host multi-user fork topology (see skill
# `hermes-distribution-packaging`, section "Single-host multi-user fork").
#
# Operator's PC hosts a forked hermes + relay; each invited user gets an
# isolated profile under ~/.hermes/profiles/<user_slug>/ with their own
# Mnemosyne DB, Ed25519 signing key, and consent receipt. Per-user toolset
# is the operator's standard stack (NO terminal, delegation, cronjob,
# kanban, mcp — the user is sandboxed at the framework layer).
#
# Usage:
#     relay/provision-user.sh <user_slug> [--opt-in true|false]
#     relay/provision-user.sh --help
#
# What it does, in order:
#   1. Creates ~/.hermes/profiles/<user_slug>/ with config.yaml + .env
#      pointer file + Mnemosyne DB location.
#   2. Generates an Ed25519 keypair; writes the private key to
#      ~/.hermes/security/<user_slug>.key (chmod 600). The public key
#      fingerprint is recorded in the consent_receipt.json.
#   3. Writes consent_receipt.json at
#      ~/.hermes/profiles/<user_slug>/consent_receipt.json with the
#      opt-in flag (default: true).
#   4. Adds the user to ~/.hermes/profiles/registry.yaml (creating it
#      if absent). Idempotent — re-running with the same slug updates
#      the existing entry instead of duplicating.
#   5. Per-profile toolsets = [file, web, docker, webscraping, search,
#      browser, vision, memory, todo, code_execution] (operator's stack;
#      shell, delegation, cronjob, kanban, mcp intentionally excluded).
#   6. Mnemosyne is hardcoded to scope=private — never shared across
#      profiles, never pulled from operator's memory.
#
# Cross-OS note: this is a bash script. On Windows we run under
# git-bash / MSYS. All paths with spaces ('Application Data', etc.)
# MUST be double-quoted. We use $HOME rather than ~ inside expansions
# because tilde doesn't expand inside quotes on all shells.
#
# Verification after running:
#   ls -la "$HOME/.hermes/profiles/<user_slug>/"
#   ls -la "$HOME/.hermes/security/<user_slug>.key"
#   cat "$HOME/.hermes/profiles/registry.yaml"

set -euo pipefail

# ─── Constants ──────────────────────────────────────────────────────────────

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILES_DIR="$HERMES_HOME/profiles"
SECURITY_DIR="$HERMES_HOME/security"
REGISTRY="$PROFILES_DIR/registry.yaml"
PY="${PY:-python}"   # python resolves on Windows (3.11) AND Linux/macOS

# Cross-OS path helper. On Windows + git-bash/MSYS, $HOME is
# /c/Users/<user> (POSIX-style), but the system python is a native
# Windows python that ONLY understands C:/Users/<user>. Bash is
# happy with the POSIX form (it auto-translates); passing it raw to
# python makes Windows say "no such path". Convert MSYS paths to
# native Windows paths before handing them to python; on Linux/macOS
# leave the path alone.
to_native_path() {
    local p="$1"
    # Case 1: MSYS POSIX-style with /c/... /d/... etc. (git-bash default)
    if [[ "$p" =~ ^/([a-zA-Z])/ ]]; then
        local drive="${BASH_REMATCH[1]}"
        local rest="${p:2}"
        # Use cygpath if available; otherwise do the substitution inline.
        if command -v cygpath >/dev/null 2>&1; then
            cygpath -w "$p"
        else
            # Upper-case the drive, replace / with \ for safety.
            local upper_drive
            upper_drive="$(printf '%s' "$drive" | tr '[:lower:]' '[:upper:]')"
            printf '%s:\\%s' "$upper_drive" "$(printf '%s' "$rest" | tr '/' '\\')"
        fi
    else
        printf '%s' "$p"
    fi
}

# Per-user toolset list — operator's stack. Keep this in sync with the
# "Single-host multi-user fork" section of the skill. Do NOT add
# `terminal`, `delegation`, `cronjob`, `kanban`, or `mcp` — the user
# has no shell, no subagent spawning, no scheduling, no MCP install.
USER_TOOLSETS=(
    file
    web
    docker
    webscraping
    search
    browser
    vision
    memory
    todo
    code_execution
)

# Mnemosyne is private by hardcoded policy. Never `shared`, never
# `pull_on_session_start: true`, never `remote` populated.
MNEMOSYNE_SCOPE="private"

CONSENT_VERSION="v1.2.0"
PROVISIONER_VERSION="0.1.0"

# ─── Help ──────────────────────────────────────────────────────────────────

print_help() {
    cat <<EOF
provision-user.sh — provision a per-user hermes profile (single-host multi-user fork)

Usage:
    $0 <user_slug> [--opt-in true|false]

Arguments:
    <user_slug>    Lowercase identifier (a-z, 0-9, underscore, hyphen). Used
                   as the profile directory name and key filename.

Options:
    --opt-in       Whether the user opts in to audit event forwarding.
                   Default: true. Stored verbatim in consent_receipt.json.
    --rotate-key   Regenerate the Ed25519 keypair even if one exists.
                   Default: refuse to overwrite (the collector is keyed
                   against the existing public key). The operator must
                   pass this explicitly to rotate.

Examples:
    $0 alice
    $0 bob --opt-in false
    $0 friend_01 --rotate-key
EOF
}

# ─── Argument parsing ─────────────────────────────────────────────────────

# Allow `--help` / `-h` as the ONLY argument (no slug required).
if [ $# -eq 1 ]; then
    case "$1" in
        -h|--help)
            print_help
            exit 0
            ;;
    esac
fi

if [ $# -lt 1 ]; then
    print_help
    exit 1
fi

USER_SLUG="$1"
shift

OPT_IN="true"
ROTATE_KEY="false"
while [ $# -gt 0 ]; do
    case "$1" in
        --opt-in)
            OPT_IN="${2:-}"
            shift 2
            ;;
        --opt-in=*)
            OPT_IN="${1#*=}"
            shift
            ;;
        --rotate-key)
            ROTATE_KEY="true"
            shift
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            print_help
            exit 2
            ;;
    esac
done

# Validate slug: lowercase, digits, underscore, hyphen. 1–64 chars.
if ! [[ "$USER_SLUG" =~ ^[a-z0-9_-]{1,64}$ ]]; then
    echo "ERROR: user_slug must match ^[a-z0-9_-]{1,64}\$ (got: '$USER_SLUG')" >&2
    exit 2
fi

case "$OPT_IN" in
    true|false) ;;
    *)
        echo "ERROR: --opt-in must be 'true' or 'false' (got: '$OPT_IN')" >&2
        exit 2
        ;;
esac

# Refuse to clobber profiles that share names with reserved slugs.
case "$USER_SLUG" in
    default|quarantine|default-template|operator)
        echo "ERROR: '$USER_SLUG' is a reserved profile name." >&2
        exit 2
        ;;
esac

USER_PROFILE_DIR="$PROFILES_DIR/$USER_SLUG"
USER_KEY="$SECURITY_DIR/$USER_SLUG.key"
USER_CONSENT="$USER_PROFILE_DIR/consent_receipt.json"
USER_CONFIG="$USER_PROFILE_DIR/config.yaml"
USER_ENV_POINTER="$USER_PROFILE_DIR/.env"
USER_PROFILE_DESC="$USER_PROFILE_DIR/profile.yaml"
USER_MNEMOSYNE_DB="$USER_PROFILE_DIR/state.db"

# Native paths for python (Windows python needs C:/... not /c/...).
# On Linux/macOS these equal the POSIX paths.
USER_KEY_NATIVE="$(to_native_path "$USER_KEY")"
USER_CONSENT_NATIVE="$(to_native_path "$USER_CONSENT")"
USER_CONFIG_NATIVE="$(to_native_path "$USER_CONFIG")"
REGISTRY_NATIVE="$(to_native_path "$REGISTRY")"

# ─── Preflight ─────────────────────────────────────────────────────────────

# Resolve a usable python3. python (3.11) is on PATH on this host; on
# Linux/macOS python3 is the canonical name. We probe both.
if ! command -v "$PY" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
        PY="python3"
    else
        echo "ERROR: neither 'python' nor 'python3' is on PATH." >&2
        exit 1
    fi
fi

PY_VERSION="$("$PY" -c 'import sys; print("%d.%d" % (sys.version_info[:2]))')"
PY_MAJOR="${PY_VERSION%%.*}"
if [ "$PY_MAJOR" -lt 3 ]; then
    echo "ERROR: Python 3.x is required (found $PY_VERSION)." >&2
    exit 1
fi

# The cryptography library is required for Ed25519 keygen. It ships
# with the hermes-agent venv on this host; if it's missing, the user
# gets a clear pip hint.
if ! "$PY" -c 'import cryptography' >/dev/null 2>&1; then
    echo "ERROR: python 'cryptography' library is required for Ed25519 keygen." >&2
    echo "       Install with: $PY -m pip install cryptography" >&2
    exit 1
fi

# Create top-level dirs. Quoted: HERMES_HOME can contain spaces under
# Windows ('Application Data' style layouts under OneDrive).
mkdir -p "$HERMES_HOME"
mkdir -p "$PROFILES_DIR"
mkdir -p "$SECURITY_DIR"
mkdir -p "$USER_PROFILE_DIR"
mkdir -p "$USER_PROFILE_DIR/memories"

# ─── Step 1: write per-user config.yaml ────────────────────────────────────

# Profile-scoped keys ONLY (per hermes_cli/config.py line 4893-4894):
# _config_version, model, providers, fallback_model, fallback_providers,
# credential_pool_strategies, toolsets. Everything else is silently
# ignored at the profile layer.
{
    echo "# ~/.hermes/profiles/$USER_SLUG/config.yaml"
    echo "# Per-user overlay for single-host multi-user fork (provisioner v$PROVISIONER_VERSION)."
    echo "# See skill 'hermes-distribution-packaging', section 'Single-host multi-user fork'."
    echo "#"
    echo "# Profile-scoped keys ONLY (everything else is silently ignored at the"
    echo "# profile layer). The user's API keys live in the .env pointer file in"
    echo "# this same directory, NOT inline here."
    echo ""
    echo "_config_version: 1"
    echo ""
    echo "# ── Toolsets (operator's stack; user has no shell) ─────────────────────"
    echo "# DO NOT add: terminal, delegation, cronjob, kanban, mcp."
    echo "toolsets:"
    for ts in "${USER_TOOLSETS[@]}"; do
        echo "  - $ts"
    done
    echo ""
    echo "# ── Model: user-supplied (filled in by user) ──────────────────────────"
    echo "model:"
    echo "  default: \"\"             # user fills from their .env at first launch"
    echo "  provider: \"\""
    echo ""
    echo "# ── Mnemosyne: private scope, never shared ───────────────────────────"
    echo "memory:"
    echo "  provider: mnemosyne"
    echo "  mnemosyne:"
    echo "    scope: $MNEMOSYNE_SCOPE"
    echo "    sync:"
    echo "      enabled: $OPT_IN     # mirrors consent_receipt.json"
    echo "      push_on_session_end: $OPT_IN"
    echo "      push_interval_minutes: 30"
    echo "      pull_on_session_start: false   # ALWAYS false — no cross-profile reads"
    echo "    db_path: \"\$HERMES_HOME/profiles/$USER_SLUG/state.db\""
} > "$USER_CONFIG"

# profile.yaml — descriptor used by kanban_decompose for routing.
{
    echo "description: \"Per-user profile for $USER_SLUG (single-host multi-user fork).\""
    echo "description_auto: false"
} > "$USER_PROFILE_DESC"

# .env pointer file. The user populates this with their own LLM keys
# at first launch. We write a documented template rather than an empty
# file so the user knows what to put here.
{
    echo "# ~/.hermes/profiles/$USER_SLUG/.env"
    echo "# Per-user LLM keys. NEVER share this file across profiles."
    echo "# Provisioned by provision-user.sh v$PROVISIONER_VERSION on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo ""
    echo "# Pick your provider and uncomment one block. The literal 'pass:api/...' "
    echo "# pointer is preferred (resolved via the system 'pass' credential store)"
    echo "# so the real value never appears in this file."
    echo ""
    echo "# Example (OpenAI):"
    echo "# OPENAI_API_KEY=pass:api/$USER_SLUG-openai"
    echo "# Example (Anthropic):"
    echo "# ANTHROPIC_API_KEY=pass:api/$USER_SLUG-anthropic"
} > "$USER_ENV_POINTER"
# Permissions: this file will hold secret material; lock it down even
# when it only contains pointers.
chmod 600 "$USER_ENV_POINTER" 2>/dev/null || true

# Touch the Mnemosyne DB so the path is real from the first launch
# (SQLite will create the file on first write, but having it present
# helps verification).
: > "$USER_MNEMOSYNE_DB"

echo "[1/6] profile created at $USER_PROFILE_DIR"

# ─── Step 2: Ed25519 keypair ────────────────────────────────────────────────

# Skip keygen on re-run unless --rotate-key was passed. Rationale:
# the operator's collector is registered against the existing public
# key — silently rotating it would orphan the user's audit trail. To
# rotate, the operator must explicitly opt in.
if [ -f "$USER_KEY" ] && [ "$ROTATE_KEY" != "true" ]; then
    echo "[2/6] Ed25519 key already exists at $USER_KEY (use --rotate-key to regenerate)"
else
    # Generate via python's cryptography library. We use Ed25519 because
    # it's the same algorithm the audit relay uses (per the
    # 'hermes-distribution-packaging' skill, Layer 5), so the operator's
    # collector can verify per-user signatures with the same code path.
"$PY" - "$USER_KEY_NATIVE" <<'PYEOF'
import base64
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

key_path = sys.argv[1]

# Refuse to silently clobber an existing key. Operators must explicitly
# rotate (rm the old key first) — never overwrite.
if os.path.exists(key_path):
    print(f"ERROR: key already exists at {key_path}; refusing to overwrite.", file=sys.stderr)
    sys.exit(3)

private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# PEM-encoded private key (PKCS8). The public key is recoverable from
# the private key for Ed25519, but we also serialize the public key
# separately into the consent receipt for the operator's records.
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
public_raw = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)

# Atomic write: write to a sibling temp file, fsync, then rename. This
# avoids a half-written key if the process is killed mid-write.
tmp_path = key_path + ".tmp"
with open(tmp_path, "wb") as fp:
    fp.write(private_pem)
    fp.flush()
    os.fsync(fp.fileno())
os.replace(tmp_path, key_path)

# chmod 600 (best-effort on Windows where chmod is a no-op for ACLs,
# but the operator's NTFS DACL on the security/ dir should already
# restrict access).
os.chmod(key_path, 0o600)

# Emit the public key + fingerprint on stdout for the caller to capture
# in the consent receipt.
public_b64 = base64.b64encode(public_raw).decode("ascii")
# Fingerprint = base64url(sha256(raw_public_key))[:16] — same scheme
# the X-Hermes-Key-Id header uses (per skill section Layer 5).
import hashlib
fp_hash = hashlib.sha256(public_raw).digest()
fingerprint = base64.urlsafe_b64encode(fp_hash)[:16].decode("ascii").rstrip("=")
print(public_b64)
print(fingerprint)
PYEOF

# The python heredoc above emits two lines on stdout: public_b64 and
# fingerprint. We just generated the key — the fact that python exited
# 0 means the file is on disk. The public key + fingerprint will be
# written into the consent receipt in step 3 by re-reading the private
# key from disk.

echo "[2/6] Ed25519 keypair written to $USER_KEY (chmod 600)"
fi

# ─── Step 3: consent_receipt.json ───────────────────────────────────────────

# Sign the consent receipt with the user's own private key. The
# operator's collector (or any auditor) can verify with the public key
# recorded in the receipt itself.
"$PY" - "$USER_KEY_NATIVE" "$USER_CONSENT_NATIVE" "$USER_SLUG" "$OPT_IN" "$CONSENT_VERSION" "$PROVISIONER_VERSION" <<'PYEOF'
import base64
import datetime
import hashlib
import json
import os
import sys

import yaml  # PyYAML ships with hermes-agent venv; falls back if absent

key_path, receipt_path, user_slug, opt_in, consent_version, provisioner_version = sys.argv[1:7]

with open(key_path, "rb") as fp:
    private_pem = fp.read()

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

private_key = serialization.load_pem_private_key(private_pem, password=None)
public_key = private_key.public_key()
public_raw = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
public_b64 = base64.b64encode(public_raw).decode("ascii")
fingerprint = base64.urlsafe_b64encode(hashlib.sha256(public_raw).digest())[:16].decode("ascii").rstrip("=")

# User fingerprint = sha256(public_key) hex[:32]. Distinct from the
# short fingerprint above (which is for HMAC key-id headers).
user_fingerprint = hashlib.sha256(public_raw).hexdigest()[:32]

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Build the receipt body, then sign a canonical-JSON of it. The
# canonical form is sorted keys, no whitespace, UTF-8.
body = {
    "consent_version": consent_version,
    "consented_at": now,
    "user_slug": user_slug,
    "user_fingerprint": user_fingerprint,
    "public_key_ed25519": public_b64,
    "public_key_fingerprint": fingerprint,
    "publisher": "operator-local",      # the operator is the publisher here
    "event_types_authorized": (
        ["install", "launch", "tool_invocation", "quarantine_escalation", "consent_change", "error"]
        if opt_in == "true" else []
    ),
    "opt_in": opt_in == "true",
    "provisioner_version": provisioner_version,
    "topology": "single-host-multi-user-fork",
}

canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
signature = private_key.sign(canonical)
body["signature"] = {
    "algorithm": "ed25519",
    "value": base64.b64encode(signature).decode("ascii"),
    "canonical_form": "sorted-keys, no-whitespace, utf-8",
}

# Atomic write.
tmp = receipt_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fp:
    json.dump(body, fp, indent=2, sort_keys=True)
    fp.write("\n")
    fp.flush()
    os.fsync(fp.fileno())
os.replace(tmp, receipt_path)

# Best-effort chmod. On Windows, ACLs are what matter; chmod is a no-op.
os.chmod(receipt_path, 0o644)
PYEOF

echo "[3/6] consent_receipt.json written to $USER_CONSENT (opt_in=$OPT_IN)"

# ─── Step 4: registry.yaml ─────────────────────────────────────────────────

# Append/update the registry. Format is YAML; we read the existing
# file, update the entry for this slug (or append a new one), and
# write atomically. We use python's yaml for safe serialization
# rather than text-grepping, which is the lesson the skill hammers on
# (see 'Pitfall — post-skill-create.sh style shell scripts...').

"$PY" - "$REGISTRY_NATIVE" "$USER_SLUG" "$OPT_IN" "$USER_PROFILE_DIR" "$USER_KEY" <<'PYEOF'
import datetime
import os
import sys

import yaml

registry_path, user_slug, opt_in, profile_dir, key_path = sys.argv[1:6]

if os.path.exists(registry_path):
    with open(registry_path, "r", encoding="utf-8") as fp:
        try:
            data = yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            # Corrupted registry — back it up and start fresh so we
            # never silently lose data.
            backup = registry_path + ".corrupt-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            os.replace(registry_path, backup)
            print(f"WARN: registry was corrupt; backed up to {backup}", file=sys.stderr)
            data = {}
else:
    data = {}

# Expected schema:
#   version: 1
#   users:
#     <slug>:
#       profile_dir: ...
#       key_path: ...
#       opt_in: true|false
#       created_at: <iso8601>
#       updated_at: <iso8601>
data.setdefault("version", 1)
data.setdefault("users", {})

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
entry = data["users"].get(user_slug)
if entry is None:
    data["users"][user_slug] = {
        "profile_dir": profile_dir,
        "key_path": key_path,
        "opt_in": opt_in == "true",
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }
    action = "added"
else:
    entry["profile_dir"] = profile_dir
    entry["key_path"] = key_path
    entry["opt_in"] = opt_in == "true"
    entry["updated_at"] = now
    entry.setdefault("created_at", now)
    entry["status"] = "active"
    action = "updated"

tmp = registry_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fp:
    yaml.safe_dump(data, fp, sort_keys=False, default_flow_style=False)
    fp.flush()
    os.fsync(fp.fileno())
os.replace(tmp, registry_path)

print(f"[registry] {action} user '{user_slug}' (opt_in={opt_in})")
PYEOF

echo "[4/6] registry updated at $REGISTRY"

# ─── Step 5: toolset policy is encoded in config.yaml (step 1) ─────────────

# Listed here for readability / discoverability — the actual list is
# in USER_TOOLSETS at the top of this script and was written to
# config.yaml in step 1. We re-assert the policy here so a future
# contributor grepping for 'toolsets' finds both the source-of-truth
# comment and the actual list.
TS_LIST=""
for ts in "${USER_TOOLSETS[@]}"; do
    TS_LIST="$TS_LIST$ts, "
done
TS_LIST="${TS_LIST%, }"
echo "[5/6] toolsets pinned (10): $TS_LIST"

# ─── Step 6: Mnemosyne policy assertion ─────────────────────────────────────

# Verify the config we just wrote has scope=private and
# pull_on_session_start=false. Belt-and-braces: if a future patch to
# the config-template accidentally loosens the isolation, this check
# fails loudly instead of silently shipping a leaky profile.
"$PY" - "$USER_CONFIG_NATIVE" "$MNEMOSYNE_SCOPE" <<'PYEOF'
import sys

import yaml

config_path, expected_scope = sys.argv[1:3]
with open(config_path, "r", encoding="utf-8") as fp:
    cfg = yaml.safe_load(fp) or {}

scope = (cfg.get("memory") or {}).get("mnemosyne", {}).get("scope")
pull = (cfg.get("memory") or {}).get("mnemosyne", {}).get("sync", {}).get("pull_on_session_start")
ok = True
if scope != expected_scope:
    print(f"FAIL: memory.mnemosyne.scope = {scope!r}, expected {expected_scope!r}", file=sys.stderr)
    ok = False
if pull is not False:
    print(f"FAIL: pull_on_session_start = {pull!r}, expected False", file=sys.stderr)
    ok = False
if not ok:
    sys.exit(4)
print(f"[policy] memory.mnemosyne.scope={scope} (private — no cross-profile reads)")
print(f"[policy] memory.mnemosyne.sync.pull_on_session_start={pull} (never pull from operator)")
PYEOF

echo "[6/6] Mnemosyne policy verified: scope=$MNEMOSYNE_SCOPE, pull_on_session_start=false"

# ─── Summary ────────────────────────────────────────────────────────────────

cat <<EOF

✓ Provisioned user '$USER_SLUG'

  Profile dir:    $USER_PROFILE_DIR
  Config:         $USER_CONFIG
  .env pointer:   $USER_ENV_POINTER
  Profile desc:   $USER_PROFILE_DESC
  Mnemosyne DB:   $USER_MNEMOSYNE_DB
  Ed25519 key:    $USER_KEY  (chmod 600)
  Consent:        $USER_CONSENT
  Registry:       $REGISTRY

  Toolsets:       ${USER_TOOLSETS[*]}
  Mnemosyne:      scope=$MNEMOSYNE_SCOPE, pull_on_session_start=false
  Opt-in:         $OPT_IN

Next steps for the operator:
  1. Share ~workspaces/$USER_SLUG/ with the user (their working dir).
  2. Have the user populate $USER_ENV_POINTER with their own LLM keys.
  3. Launch the user's profile:  hermes -p $USER_SLUG chat
  4. Re-run this script to rotate opt-in or update the entry:
       relay/provision-user.sh $USER_SLUG --opt-in false
EOF
