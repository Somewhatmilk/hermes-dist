#!/usr/bin/env python3
"""
hermes-dist-operator — operator-side CLI for managing hermes-dist distribution.

Subcommands:
    publish      Push a new SOUL.md + config.yaml to all users (or a rollout %)
    rollback     Restore the previous manifest version
    installed    List which user is running which version
    show         Show the current latest manifest
    pin-user     Pin a specific user to a specific version (skip updates)
    unpin-user   Remove a user pin

Reads:
    OPERATOR_TOKEN     env var (required)
    RELAY_URL          env var (default: https://relay.local)
    REPO_DIR           env var (default: ~/hermes-dist)
    SOUL_MD_PATH       env var (default: $REPO_DIR/default-template/SOUL.md)
    CONFIG_YAML_PATH   env var (default: $REPO_DIR/default-template/config.yaml)
    HERMES_VERSION     env var (default: 0.4.2) — what hermes version to require

All commands hit the relay via HTTPS. The operator's laptop doesn't need
direct access to user installs.
"""

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


RELAY_URL = os.environ.get("RELAY_URL", "https://relay.local")
OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN", "")
REPO_DIR = Path(os.environ.get("REPO_DIR", str(Path.home() / "hermes-dist")))
SOUL_MD_PATH = Path(os.environ.get("SOUL_MD_PATH", str(REPO_DIR / "default-template" / "SOUL.md")))
CONFIG_YAML_PATH = Path(os.environ.get("CONFIG_YAML_PATH", str(REPO_DIR / "default-template" / "config.yaml")))
HERMES_VERSION = os.environ.get("HERMES_VERSION", "0.4.2")


def _post(path: str, payload: dict, auth_header: tuple[str, str] | None = None) -> dict:
    url = f"{RELAY_URL.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers[auth_header[0]] = auth_header[1]
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ✗ HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def _get(path: str, auth_header: tuple[str, str] | None = None) -> dict:
    url = f"{RELAY_URL.rstrip('/')}{path}"
    headers = {}
    if auth_header:
        headers[auth_header[0]] = auth_header[1]
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ✗ HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def require_operator_token() -> str:
    if not OPERATOR_TOKEN:
        print("  ✗ OPERATOR_TOKEN env var not set", file=sys.stderr)
        print("    Set it in ~/.hermes-dist-operator.env or export it before running", file=sys.stderr)
        sys.exit(1)
    return OPERATOR_TOKEN


def next_soul_version(current: str | None) -> str:
    """Bump a monotonic version counter. Format: vNN."""
    if not current:
        return "v1"
    try:
        n = int(current.lstrip("v"))
        return f"v{n + 1}"
    except ValueError:
        # First version that doesn't follow the pattern; reset
        return "v1"


def cmd_show(_args):
    token = require_operator_token()
    latest = _get("/api/v1/manifest?uuid=00000000-0000-0000-0000-000000000000",
                  ("X-Operator-Token", token))
    print(json.dumps(latest, indent=2))


def cmd_publish(args):
    token = require_operator_token()

    if not SOUL_MD_PATH.exists():
        print(f"  ✗ SOUL.md not found at {SOUL_MD_PATH}", file=sys.stderr)
        sys.exit(1)
    if not CONFIG_YAML_PATH.exists():
        print(f"  ✗ config.yaml not found at {CONFIG_YAML_PATH}", file=sys.stderr)
        sys.exit(1)

    soul_md = SOUL_MD_PATH.read_text(encoding="utf-8")
    config_yaml = CONFIG_YAML_PATH.read_text(encoding="utf-8")

    soul_version = args.soul_version
    if not soul_version:
        # Auto-bump: read current latest, increment
        current = _get("/api/v1/installed", ("X-Operator-Token", token))
        # No "current soul version" endpoint without specifying user;
        # use the publish endpoint which is idempotent on (soul_md_version).
        # For auto-bump, fetch the highest known soul_md_version from
        # the audit log. Simple approach: try v1..v999 and find an unused one.
        # For the small-group PoC, the operator passes --soul-version explicitly.
        soul_version = "v1"
        for n in range(1, 1000):
            candidate = f"v{n}"
            try:
                _post("/api/v1/release",
                      {"soul_md_version": candidate,
                       "config_yaml_version": candidate,
                       "hermes_version": HERMES_VERSION,
                       "soul_md": soul_md,
                       "config_yaml": config_yaml,
                       "rollout_pct": args.rollout_pct,
                       "message": args.message or ""},
                      ("X-Operator-Token", token))
                soul_version = candidate
                break
            except SystemExit:
                continue

    resp = _post("/api/v1/release",
                 {"soul_md_version": soul_version,
                  "config_yaml_version": soul_version,
                  "hermes_version": HERMES_VERSION,
                  "soul_md": soul_md,
                  "config_yaml": config_yaml,
                  "rollout_pct": args.rollout_pct,
                  "message": args.message or ""},
                 ("X-Operator-Token", token))

    print(f"  ✓ Published {resp['soul_md_version']} (id={resp['version_id']})")
    print(f"    Rollout: {args.rollout_pct}%")
    print(f"    Hermes version pinned: {HERMES_VERSION}")
    print(f"    SOUL.md source: {SOUL_MD_PATH}")
    print(f"    config.yaml source: {CONFIG_YAML_PATH}")
    print()
    print("    All users will pick this up on their next heartbeat (≤30s).")
    print("    Verify with:  hermes-dist-operator installed")


def cmd_installed(_args):
    token = require_operator_token()
    resp = _get("/api/v1/installed", ("X-Operator-Token", token))
    print(f"=== {resp['count']} users ===")
    for u in resp["users"]:
        soul = u.get("soul_md_version") or "—"
        cfg = u.get("config_yaml_version") or "—"
        last = u.get("last_heartbeat_at") or "never"
        os_name = u.get("os") or "?"
        hermes = u.get("hermes_installed") or "?"
        print(f"  {u['user_uuid'][:8]}...  os={os_name:<8}  hermes={hermes:<8}  soul={soul:<5}  cfg={cfg:<5}  last_beat={last}")


def cmd_rollback(args):
    """Rollback to a previous soul_md_version."""
    token = require_operator_token()

    if args.to:
        target = args.to
    else:
        # Get latest, decrement by 1
        installed = _get("/api/v1/installed", ("X-Operator-Token", token))
        # We need /api/v1/manifest-history; for now, hard require --to.
        print("  ✗ Auto-rollback requires /api/v1/manifest-history (TODO)", file=sys.stderr)
        print("    Use --to vNN explicitly", file=sys.stderr)
        sys.exit(1)

    # Re-publish an old version's content. For the PoC, the operator keeps
    # the old SOUL.md in git history; checkout + publish.
    print(f"  → Rolling back to {target}")
    print("    This re-publishes whatever SOUL.md you have checked out.")
    print("    Make sure `git checkout {target} -- default-template/` first.")
    cmd_publish(args)


def cmd_pin_user(args):
    token = require_operator_token()
    print(f"  → Pinning user {args.user_uuid} to {args.soul_version}")
    # TODO: when pinned, /api/v1/manifest should return that pinned version
    # regardless of latest. Requires a `user_pins` table.
    print("  ⚠ Pin feature requires manifest_store.user_pins table (TODO)")


def main():
    parser = argparse.ArgumentParser(prog="hermes-dist-operator",
                                     description="Operator CLI for hermes-dist")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show current latest manifest")
    p_show.set_defaults(func=cmd_show)

    p_pub = sub.add_parser("publish", help="Push a new SOUL.md + config.yaml")
    p_pub.add_argument("--soul-version", help="Explicit version (e.g. v3). Auto-bumps if omitted.")
    p_pub.add_argument("--rollout-pct", type=int, default=100, help="Percentage of users to roll out to (1..100)")
    p_pub.add_argument("--message", default="", help="Human-readable release notes")
    p_pub.set_defaults(func=cmd_publish)

    p_inst = sub.add_parser("installed", help="List users and what they're running")
    p_inst.set_defaults(func=cmd_installed)

    p_rb = sub.add_parser("rollback", help="Republish a previous version")
    p_rb.add_argument("--to", required=True, help="Target version (e.g. v3)")
    p_rb.add_argument("--rollout-pct", type=int, default=100)
    p_rb.add_argument("--message", default="Rollback")
    p_rb.set_defaults(func=cmd_rollback)

    p_pin = sub.add_parser("pin-user", help="Pin a user to a specific version")
    p_pin.add_argument("user_uuid")
    p_pin.add_argument("soul_version")
    p_pin.set_defaults(func=cmd_pin_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()