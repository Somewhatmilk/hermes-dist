"""
HMAC authentication for hermes-dist relay.

Each user install gets a per-user HMAC secret at first launch. The relay
verifies the signature on every inbound request. No secret = no request
gets through, no exceptions.

Wire format:
  X-Hermes-User:      <user_uuid>
  X-Hermes-Timestamp: <ISO 8601 UTC, e.g. 2026-07-06T12:34:56Z>
  X-Hermes-Nonce:     <uuid, prevents replay>
  X-Hermes-Signature: <base64(HMAC-SHA256(secret, canonical_string))>

Canonical string (newline-joined):
  <user_uuid>
  <timestamp>
  <nonce>
  <event_type>
  <raw_body>

Replay defense:
  - Timestamp must be within ±300s of server time
  - Nonce stored in memory for 60s; any second use is rejected.
  T9 (Tailscale board) tightened the replay window from 600s → 60s so that
  Layer A catches a chatty agent that re-sends within a minute even if it
  rolls the nonce. Layers B (content-hash dedup) and C (tool_invocation
  coalesce) live in sqlite_store.py + main.py.
"""

import base64
import hmac
import hashlib
import os
import re
import time
from collections import defaultdict
from typing import Optional

from fastapi import Header, HTTPException, Request, status


# ─── Nonce store (in-memory for the PoC) ───────────────────────────────────
# In production this would be Redis. For a <20 user PoC, in-memory is fine
# as long as we restart-on-deploy (which we do, see the systemd unit).

class NonceStore:
    def __init__(self, ttl_seconds: int = 60):
        # T9: was 600s. Tightened to 60s — a chatty agent that re-sends the
        # same body inside a minute is suspicious and should be caught by
        # Layer A even when the nonce differs.
        self.ttl = ttl_seconds
        self._seen: dict[str, float] = defaultdict(float)

    def check_and_record(self, nonce: str) -> bool:
        """Returns True if nonce is fresh, False if already seen."""
        now = time.time()
        # Prune expired entries
        expired = [k for k, v in self._seen.items() if now - v > self.ttl]
        for k in expired:
            del self._seen[k]

        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


_nonce_store = NonceStore()


# ─── Timestamp validation ──────────────────────────────────────────────────

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CLOCK_SKEW_SECONDS = 300


def validate_timestamp(ts: str) -> None:
    """Raises HTTPException if timestamp is malformed or too old/future."""
    if not TIMESTAMP_RE.match(ts):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid timestamp format (must be ISO 8601 UTC with Z suffix)"
        )
    # Parse and check skew
    try:
        from datetime import datetime, timezone
        event_time = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = abs((now - event_time).total_seconds())
        if delta > CLOCK_SKEW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Timestamp out of range (skew {delta:.0f}s > {CLOCK_SKEW_SECONDS}s)"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid timestamp: {e}"
        )


# ─── Signature verification ────────────────────────────────────────────────

def compute_signature(secret: str, canonical: str) -> str:
    """Returns base64(HMAC-SHA256(secret, canonical))."""
    mac = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode("ascii")


def verify_signature(secret: str, canonical: str, provided: str) -> bool:
    """Constant-time signature verification."""
    expected = compute_signature(secret, canonical)
    return hmac.compare_digest(expected, provided)


# ─── FastAPI dependency ────────────────────────────────────────────────────

async def verify_hmac_request(
    request: Request,
    x_hermes_user: str = Header(..., min_length=32, max_length=64),
    x_hermes_timestamp: str = Header(...),
    x_hermes_nonce: str = Header(..., min_length=32, max_length=64),
    x_hermes_signature: str = Header(...),
    x_hermes_event_type: str = Header(..., min_length=1, max_length=64),
) -> dict:
    """
    FastAPI dependency that verifies a HMAC-signed request.

    Returns a dict with user_uuid, event_type, body_bytes for the handler.
    Raises HTTPException on any failure.
    """
    # 1. Validate UUID format
    uuid_re = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
    if not uuid_re.match(x_hermes_user):
        raise HTTPException(status_code=401, detail="Invalid user UUID format")

    # 2. Validate timestamp
    validate_timestamp(x_hermes_timestamp)

    # 3. Check nonce (replay defense)
    if not _nonce_store.check_and_record(x_hermes_nonce):
        raise HTTPException(status_code=401, detail="Nonce already seen (replay rejected)")

    # 4. Read body and compute canonical
    body_bytes = await request.body()
    canonical = "\n".join([
        x_hermes_user,
        x_hermes_timestamp,
        x_hermes_nonce,
        x_hermes_event_type,
        body_bytes.decode("utf-8", errors="replace")
    ])

    # 5. Look up user secret and verify
    from .sqlite_store import get_user_secret
    secret = get_user_secret(x_hermes_user)
    if not secret:
        raise HTTPException(status_code=401, detail="Unknown user (not registered)")

    if not verify_signature(secret, canonical, x_hermes_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    return {
        "user_uuid": x_hermes_user,
        "event_type": x_hermes_event_type,
        "body_bytes": body_bytes,
    }
