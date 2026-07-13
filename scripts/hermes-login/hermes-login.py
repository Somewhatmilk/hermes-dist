#!/usr/bin/env python3
"""hermes login - issue + store capability token for operator relay.

Pattern (per T9):
  Linux/macOS: this script called directly
  Windows: Service.cmd -> bash.exe -> this script

Credentials are stored in `pass` (GPG-encrypted) when available;
fall back to ~/.hermes/.operator-token (chmod 600).

Usage:
  hermes login login --operator <host.tail.ts.net> [--scope skills.read] [--scope tools.docker_run]
  hermes login status
  hermes login logout
  hermes login refresh
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timezone, timedelta

DEFAULT_SCOPES = [
    "skills.read", "skills.list",
    "tools.web_search", "tools.browser", "tools.vision",
    "mnemosyne.shared",
]
TOKEN_PATH = os.path.expanduser("~/.hermes/.operator-token")
STATE_PATH = os.path.expanduser("~/.hermes/.operator-state")
SECRET_PATH = os.path.expanduser("~/.hermes/.operator-secret")


def _load_or_register_user():
    """Load existing user_uuid from state, or register a new one."""
    if os.path.exists(STATE_PATH):
        try:
            return json.loads(open(STATE_PATH).read())["user_uuid"]
        except Exception:
            pass
    user_uuid = str(uuid.uuid4()).replace("-", "")
    state = {
        "user_uuid": user_uuid,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    os.chmod(STATE_PATH, 0o600)
    return user_uuid


def _save_token(token, payload, operator_host):
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    blob = json.dumps({"token": token, "payload": payload, "operator": operator_host,
                       "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                      indent=2)
    with open(TOKEN_PATH, "w") as f:
        f.write(blob)
    os.chmod(TOKEN_PATH, 0o600)
    # Try pass for higher security (Linux/macOS)
    try:
        import subprocess as sp
        sp.run(["pass", "insert", "hermes/operator-token"], input=blob, text=True, check=True)
        os.remove(TOKEN_PATH)
    except Exception:
        pass


def _load_token():
    if os.path.exists(TOKEN_PATH):
        try:
            return json.loads(open(TOKEN_PATH).read())
        except Exception:
            pass
    try:
        import subprocess as sp
        blob = sp.check_output(["pass", "show", "hermes/operator-token"], text=True)
        return json.loads(blob)
    except Exception:
        return None


def _sign_request(user_uuid, secret, body):
    """Build X-Hermes-* headers for HMAC signing."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = str(uuid.uuid4())
    canonical = (user_uuid + "\n" + ts + "\n" + nonce + "\nregister\n").encode() + body
    sig = base64.b64encode(
        hmac.new(secret.encode(), canonical, hashlib.sha256).digest()
    ).decode()
    return {
        "X-Hermes-User": user_uuid,
        "X-Hermes-Timestamp": ts,
        "X-Hermes-Nonce": nonce,
        "X-Hermes-Signature": sig,
    }


def cmd_login(args):
    """Register (if new) + fetch capability token."""
    user_uuid = _load_or_register_user()
    print(f"user_uuid: {user_uuid}")

    register_url = f"https://{args.operator}/api/v1/register"
    body = json.dumps({
        "uuid": user_uuid,
        "os": sys.platform,
        "version": "hermes-dist-0.5.0",
        "opted_in": True,
        "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }).encode()

    req = urllib.request.Request(
        register_url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"register failed: {e.code} {e.reason}", file=sys.stderr)
        print("If already registered, place hmac_secret at ~/.hermes/.operator-secret (chmod 600) and re-run", file=sys.stderr)
        sys.exit(1)

    if not resp.get("ok"):
        print(f"register failed: {resp}", file=sys.stderr)
        sys.exit(1)

    secret = resp.get("hmac_secret")
    if not secret:
        print("register succeeded but no hmac_secret returned (you may already be registered)", file=sys.stderr)
        sys.exit(1)

    with open(SECRET_PATH, "w") as f:
        f.write(secret)
    os.chmod(SECRET_PATH, 0o600)

    # Capability token fetch: requires a /api/v1/cap-token endpoint
    token_url = f"https://{args.operator}/api/v1/cap-token"
    scopes = args.scope or DEFAULT_SCOPES
    body = json.dumps({"scopes": scopes, "ttl_hours": args.ttl}).encode()
    headers = _sign_request(user_uuid, secret, body)
    headers["Content-Type"] = "application/json"

    req = urllib.request.Request(token_url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"cap-token failed: {e.code} {e.reason}", file=sys.stderr)
        print(f"body: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    if not resp.get("ok"):
        print(f"cap-token failed: {resp}", file=sys.stderr)
        sys.exit(1)

    token = resp["token"]
    payload = resp["payload"]
    _save_token(token, payload, args.operator)
    print(f"+ capability token saved (expires {payload['expires_at']})")
    print(f"  scopes: {payload['scopes']}")


def cmd_status(args):
    blob = _load_token()
    if not blob:
        print("not logged in. run: hermes login login --operator <host>")
        sys.exit(1)
    payload = blob["payload"]
    expires_at = datetime.fromisoformat(payload["expires_at"])
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    print(f"operator:        {blob['operator']}")
    print(f"user_uuid:       {payload['user_uuid']}")
    print(f"expires_at:      {payload['expires_at']}")
    print(f"expires_in:      {delta}")
    print(f"scopes:          {payload['scopes']}")
    print(f"saved_at:        {blob['saved_at']}")


def cmd_logout(args):
    for p in [TOKEN_PATH, STATE_PATH, SECRET_PATH]:
        if os.path.exists(p):
            os.remove(p)
            print(f"removed {p}")
    print("logged out")


def cmd_refresh(args):
    blob = _load_token()
    if not blob:
        print("not logged in. run: hermes login login --operator <host>")
        sys.exit(1)
    args.scope = blob["payload"]["scopes"]
    cmd_login(args)


def main():
    parser = argparse.ArgumentParser(prog="hermes login")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="register + fetch capability token")
    p_login.add_argument("--operator", required=True, help="operator relay host (e.g. operator.tail.ts.net)")
    p_login.add_argument("--scope", action="append", help="scope to request (can repeat)")
    p_login.add_argument("--ttl", type=int, default=24, help="token TTL in hours (default 24)")
    p_login.set_defaults(func=cmd_login)

    p_status = sub.add_parser("status", help="show current token status")
    p_status.set_defaults(func=cmd_status)

    p_logout = sub.add_parser("logout", help="remove stored token + state")
    p_logout.set_defaults(func=cmd_logout)

    p_refresh = sub.add_parser("refresh", help="refresh token (re-fetch with same scopes)")
    p_refresh.add_argument("--operator", required=True)
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()