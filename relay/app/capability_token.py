"""
HMAC capability token issuance + verification.

Each user install gets a per-user HMAC secret at register time. Capability
tokens extend that secret with scope + TTL + nonce claims, signed over the
canonical string. Tokens are short-lived (default 24h) and bound to user_uuid.

Wire format:
  X-Hermes-User:        <user_uuid>
  X-Hermes-Cap-Token:   <base64 token>

Token payload (json, signed):
  {
    "user_uuid": "a4c421af-...",
    "scopes": ["skills.read", "tools.web_search", "tools.docker_run"],
    "expires_at": "2026-08-14T00:00:00Z",
    "issued_at": "2026-07-14T12:34:56Z",
    "nonce": "<uuid>",
    "rate_limit": "60/min"
  }

Scopes (initial set):
  skills.read             - read skill content
  skills.list             - list available skills
  tools.web_search        - invoke web_search
  tools.browser           - invoke browser tools
  tools.vision            - invoke vision tools
  tools.docker_run        - submit docker run requests
  tools.skills_create     - create user-scoped skills
  mnemosyne.shared        - read shared mnemosyne surface
  profile.config_override - override default-template config

Default scope bundle for fresh users: skills.read, skills.list,
tools.web_search, tools.browser, tools.vision, mnemosyne.shared
(NO docker_run, NO config_override — those require opt-in).
"""
import base64, hashlib, hmac, json, os, time, uuid
from datetime import datetime, timezone, timedelta


DEFAULT_SCOPES = [
    "skills.read", "skills.list",
    "tools.web_search", "tools.browser", "tools.vision",
    "mnemosyne.shared",
]
DEFAULT_TTL_HOURS = 24


def issue_token(
    user_uuid: str,
    secret: str,
    scopes: list[str] | None = None,
    ttl_hours: int = DEFAULT_TTL_HOURS,
    rate_limit: str = "60/min",
) -> str:
    """Issue a capability token for user_uuid."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_uuid": user_uuid,
        "scopes": scopes or DEFAULT_SCOPES,
        "issued_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(timespec="seconds"),
        "nonce": str(uuid.uuid4()),
        "rate_limit": rate_limit,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(json.dumps({
        "payload": payload,
        "signature": base64.urlsafe_b64encode(sig).decode("utf-8"),
    }, separators=(",", ":")).encode("utf-8")).decode("utf-8")


def verify_token(token: str, user_uuid: str, secret: str) -> dict:
    """Verify + decode a capability token. Returns payload dict on success.

    Raises ValueError on:
      - bad signature
      - expired
      - user_uuid mismatch
      - malformed
    """
    try:
        outer = json.loads(base64.urlsafe_b64decode(token.encode("utf-8")))
        payload = outer["payload"]
        sig = base64.urlsafe_b64decode(outer["signature"].encode("utf-8"))
    except Exception as e:
        raise ValueError(f"malformed token: {e}") from e

    if payload.get("user_uuid") != user_uuid:
        raise ValueError("user_uuid mismatch")

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("bad signature")

    expires_at = datetime.fromisoformat(payload["expires_at"])
    if datetime.now(timezone.utc) >= expires_at:
        raise ValueError("token expired")

    return payload


def require_scope(token_payload: dict, required_scope: str) -> None:
    """Raise PermissionError if token doesn't carry required_scope."""
    if required_scope not in token_payload.get("scopes", []):
        raise PermissionError(f"missing required scope: {required_scope}")


def has_scope(token_payload: dict, scope: str) -> bool:
    """True iff token carries scope."""
    return scope in token_payload.get("scopes", [])


# CLI: print default scope bundle
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "issue":
        user_uuid = sys.argv[2]
        secret = sys.argv[3]
        token = issue_token(user_uuid, secret)
        print(token)
    elif len(sys.argv) >= 4 and sys.argv[1] == "verify":
        token, user_uuid, secret = sys.argv[2], sys.argv[3], sys.argv[4]
        try:
            print(json.dumps(verify_token(token, user_uuid, secret), indent=2))
        except ValueError as e:
            print(f"INVALID: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Default scopes: {DEFAULT_SCOPES}")
        print(f"Default TTL: {DEFAULT_TTL_HOURS}h")
        print("Usage:")
        print("  python capability_token.py issue <user_uuid> <secret>")
        print("  python capability_token.py verify <token> <user_uuid> <secret>")
