"""
Hermes Dist relay — FastAPI application.

Endpoints:
  POST   /api/v1/register        User self-registration (no auth required)
  POST   /api/v1/submit          Signed event submission (HMAC required)
  GET    /api/v1/healthz         Health check (no auth)
  GET    /api/v1/events          List events (operator auth required)
  GET    /api/v1/users           List users (operator auth required)
  GET    /api/v1/audit           List audit log (operator auth required)

Operator auth: a separate static token (env var OPERATOR_TOKEN) checked via
X-Operator-Token header. This is intentionally NOT HMAC — operators are
humans, not user installs.
"""

import os
import time
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse

from .models import (
    RegisterRequest, RegisterResponse,
    SubmitResponse, EventsResponse, UsersResponse, HealthResponse,
)
from . import sqlite_store
from .hmac_auth import verify_hmac_request


# ─── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hermes Dist Relay",
    description="Collector for hermes-dist PoC. Receives signed events from user installs.",
    version="0.1.0",
)

DB_PATH = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN", "")

START_TIME = time.time()


@app.on_event("startup")
def startup():
    sqlite_store.init_db(DB_PATH)
    if not OPERATOR_TOKEN:
        # Generate a random one and print to stdout for the operator to capture
        token = secrets.token_hex(32)
        print(f"⚠ OPERATOR_TOKEN not set. Generated random: {token}", flush=True)
        print(f"  Set this in /etc/hermes-relay/operator-token and add to .env", flush=True)
        globals()["OPERATOR_TOKEN"] = token


# ─── Operator auth ─────────────────────────────────────────────────────────

def require_operator(x_operator_token: str = Header(..., min_length=64, max_length=64)):
    if not OPERATOR_TOKEN:
        raise HTTPException(status_code=503, detail="Operator token not configured")
    if not secrets.compare_digest(x_operator_token, OPERATOR_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid operator token")
    return True


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/v1/healthz", response_model=HealthResponse)
def healthz():
    """Public health check. No auth required."""
    db_size = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
    with sqlite_store.get_conn(DB_PATH) as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    return HealthResponse(
        ok=True,
        version="hermes-relay-0.1.0",
        uptime_seconds=time.time() - START_TIME,
        db_size_mb=round(db_size, 2),
        user_count=user_count,
        event_count=event_count,
    )


@app.post("/api/v1/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    """
    User self-registration. No HMAC (the user doesn't have a secret yet).
    Returns a generated HMAC secret on first registration. The user install
    stores this and uses it for all future requests.

    Idempotent: re-registering with the same UUID returns ok=True, registered=False,
    hmac_secret=None. The user keeps their original secret.
    """
    if req.opted_in is False:
        # User opted out — record this for audit, return 200 with no secret
        # They can register again later if they change their mind
        sqlite_store.audit(DB_PATH, req.uuid, "register_opted_out", req.uuid, f"os={req.os}")
        return RegisterResponse(ok=True, registered=False, relay_version="hermes-relay-0.1.0")

    # Generate a per-user HMAC secret
    secret = secrets.token_hex(32)

    try:
        registered = sqlite_store.register_user(
            uuid_str=req.uuid,
            hmac_secret=secret,
            os=req.os,
            version=req.version,
            opted_in=req.opted_in,
            db_path=DB_PATH,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")

    if registered:
        return RegisterResponse(
            ok=True,
            registered=True,
            hmac_secret=secret,
            relay_version="hermes-relay-0.1.0",
        )
    else:
        # Already registered — don't leak the secret
        return RegisterResponse(
            ok=True,
            registered=False,
            hmac_secret=None,
            relay_version="hermes-relay-0.1.0",
        )


@app.post("/api/v1/submit", response_model=SubmitResponse)
async def submit(verified: dict = Depends(verify_hmac_request)):
    """
    HMAC-signed event submission. The verify_hmac_request dependency
    does all the signature/clock-skew/replay checking before we get here.
    """
    event_id = sqlite_store.store_event(
        uuid_str=verified["user_uuid"],
        event_type=verified["event_type"],
        payload=verified["body_bytes"],
        signature_valid=True,
        db_path=DB_PATH,
    )
    sqlite_store.audit(
        DB_PATH,
        verified["user_uuid"],
        "event_received",
        str(event_id),
        f"type={verified['event_type']} size={len(verified['body_bytes'])}",
    )
    return SubmitResponse(
        ok=True,
        event_id=event_id,
        received_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


# ─── Operator-only endpoints ───────────────────────────────────────────────

@app.get("/api/v1/events", response_model=EventsResponse, dependencies=[Depends(require_operator)])
def list_events(
    uuid: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
):
    events = sqlite_store.list_events(uuid_str=uuid, event_type=event_type, limit=limit, db_path=DB_PATH)
    return EventsResponse(ok=True, count=len(events), events=events)


@app.get("/api/v1/users", response_model=UsersResponse, dependencies=[Depends(require_operator)])
def list_users():
    users = sqlite_store.list_users(db_path=DB_PATH)
    return UsersResponse(ok=True, count=len(users), users=users)


@app.get("/api/v1/audit", dependencies=[Depends(require_operator)])
def list_audit(limit: int = 100):
    entries = sqlite_store.list_audit(limit=limit, db_path=DB_PATH)
    return {"ok": True, "count": len(entries), "entries": entries}


# ─── Root ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "hermes-dist-relay",
        "version": "0.1.0",
        "endpoints": [
            "GET  /api/v1/healthz",
            "POST /api/v1/register",
            "POST /api/v1/submit (HMAC)",
            "GET  /api/v1/events (operator)",
            "GET  /api/v1/users  (operator)",
            "GET  /api/v1/audit  (operator)",
        ],
    }
