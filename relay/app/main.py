"""
Hermes Dist relay — FastAPI application.

Endpoints:
  POST   /api/v1/register        User self-registration (no auth required)
  POST   /api/v1/submit          Signed event submission (HMAC required)
  GET    /api/v1/healthz         Health check (no auth)
  GET    /api/v1/manifest        User polls for available updates (HMAC)
  POST   /api/v1/heartbeat-ack   User reports applied version (HMAC)
  POST   /api/v1/release         Operator publishes a new manifest version (operator auth)
  GET    /api/v1/installed       Operator: who is running what (operator auth)
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
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .models import (
    RegisterRequest, RegisterResponse,
    SubmitResponse, EventsResponse, UsersResponse, HealthResponse,
)
from . import sqlite_store
from . import manifest_store
from . import scraper_jobs
from . import peer_index
from .scraper_router import ScraperPool
from . import dashboard as dashboard_router
from .hmac_auth import verify_hmac_request


# ─── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hermes Dist Relay",
    description="Collector for hermes-dist PoC. Receives signed events from user installs.",
    version="0.1.0",
)

DB_PATH = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
SCRAPER_DB_PATH = Path(os.environ.get("SCRAPER_DB_PATH", "/var/lib/hermes-relay/scraper.db"))
PEER_DB_PATH = Path(os.environ.get("PEER_DB_PATH", "/var/lib/hermes-relay/peer_index.db"))
SCRAPER_SLOT_ROOT = Path(os.environ.get("SCRAPER_SLOT_ROOT", "/var/lib/hermes-relay/scraper-slots"))
OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN", "")
MANIFEST_SIGNING_KEY = os.environ.get("MANIFEST_SIGNING_KEY", "")

START_TIME = time.time()

# Scraper pool (built at startup; rebuilt from disk on each startup)
_SCRAPER_POOL: ScraperPool | None = None


@app.on_event("startup")
def startup():
    global _SCRAPER_POOL
    sqlite_store.init_db(DB_PATH)
    manifest_store.init_manifest_db(DB_PATH)
    scraper_jobs.init_scraper_db(SCRAPER_DB_PATH)
    peer_index.init_peer_db(PEER_DB_PATH)
    _SCRAPER_POOL = ScraperPool(slot_root=SCRAPER_SLOT_ROOT)
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


# ─── Manifest (push-update channel) ────────────────────────────────────────────

class ManifestResponse(BaseModel):
    ok: bool
    soul_md_version: str = ""
    config_yaml_version: str = ""
    hermes_version: str = ""
    soul_md: str = ""           # only populated when user is behind
    config_yaml: str = ""       # only populated when user is behind
    rollout_message: str = ""
    released_at: str = ""
    user_current_soul: str = "" # for the user's log


class HeartbeatAckRequest(BaseModel):
    soul_md_version: str = Field(..., min_length=1, max_length=64)
    config_yaml_version: str = Field(..., min_length=1, max_length=64)


class ReleaseRequest(BaseModel):
    soul_md_version: str = Field(..., min_length=1, max_length=64)
    config_yaml_version: str = Field(..., min_length=1, max_length=64)
    hermes_version: str = Field(..., min_length=1, max_length=64)
    soul_md: str = Field(..., min_length=1)
    config_yaml: str = Field(..., min_length=1)
    rollout_pct: int = Field(100, ge=1, le=100)
    message: str = ""


class ReleaseResponse(BaseModel):
    ok: bool
    version_id: int
    soul_md_version: str


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


# ─── Manifest endpoints (push-update channel) ──────────────────────────────

@app.get("/api/v1/manifest", response_model=ManifestResponse)
async def get_manifest(
    uuid: str,
    verified: dict = Depends(verify_hmac_request),
):
    """
    User polls this endpoint on every heartbeat. Returns the latest manifest
    IF the user is behind on any component. Otherwise returns ok=True with
    empty content fields — keeps the heartbeat cheap when nothing has changed.
    """
    latest = manifest_store.get_latest_manifest(DB_PATH)
    if not latest:
        # No manifest yet; user keeps what they have
        sqlite_store.audit(DB_PATH, verified["user_uuid"], "manifest_empty",
                           verified["user_uuid"], "no manifest published yet")
        return ManifestResponse(ok=True)

    user_installed = manifest_store.get_user_installed(verified["user_uuid"], DB_PATH) or {}
    user_soul = user_installed.get("soul_md_version", "")
    user_cfg = user_installed.get("config_yaml_version", "")

    behind = (user_soul != latest["soul_md_version"]) or (user_cfg != latest["config_yaml_version"])

    if not behind:
        sqlite_store.audit(DB_PATH, verified["user_uuid"], "manifest_noop",
                           verified["user_uuid"], f"already on {user_soul}/{user_cfg}")
        return ManifestResponse(
            ok=True,
            soul_md_version=latest["soul_md_version"],
            config_yaml_version=latest["config_yaml_version"],
            hermes_version=latest["hermes_version"],
            user_current_soul=user_soul,
        )

    sqlite_store.audit(DB_PATH, verified["user_uuid"], "manifest_pulled",
                       verified["user_uuid"],
                       f"server={latest['soul_md_version']}/{latest['config_yaml_version']} user={user_soul}/{user_cfg}")

    return ManifestResponse(
        ok=True,
        soul_md_version=latest["soul_md_version"],
        config_yaml_version=latest["config_yaml_version"],
        hermes_version=latest["hermes_version"],
        soul_md=latest["soul_md_content"],
        config_yaml=latest["config_yaml_content"],
        rollout_message=latest["message"],
        released_at=latest["released_at"],
        user_current_soul=user_soul,
    )


@app.post("/api/v1/heartbeat-ack")
async def heartbeat_ack(
    body: HeartbeatAckRequest,
    verified: dict = Depends(verify_hmac_request),
):
    """
    User reports which version they've actually applied (post-restart).
    This is what populates the operator dashboard's "who's running what" view.
    """
    manifest_store.record_user_heartbeat(
        verified["user_uuid"],
        body.soul_md_version,
        body.config_yaml_version,
        DB_PATH,
    )
    sqlite_store.audit(DB_PATH, verified["user_uuid"], "heartbeat_ack",
                       verified["user_uuid"],
                       f"soul={body.soul_md_version} cfg={body.config_yaml_version}")
    return {"ok": True}


@app.post("/api/v1/release", response_model=ReleaseResponse, dependencies=[Depends(require_operator)])
def publish_release(body: ReleaseRequest):
    """
    Operator publishes a new manifest version. Idempotent on soul_md_version
    (republishing the same version is a no-op, returns the existing row id).
    """
    version_id = manifest_store.publish_manifest(
        soul_md_version=body.soul_md_version,
        config_yaml_version=body.config_yaml_version,
        hermes_version=body.hermes_version,
        soul_md_content=body.soul_md,
        config_yaml_content=body.config_yaml,
        released_by=os.environ.get("OPERATOR_NAME", "operator"),
        rollout_pct=body.rollout_pct,
        message=body.message,
        db_path=DB_PATH,
    )
    sqlite_store.audit(DB_PATH, "_operator", "release_published",
                       str(version_id),
                       f"version={body.soul_md_version} rollout={body.rollout_pct}%")
    return ReleaseResponse(
        ok=True,
        version_id=version_id,
        soul_md_version=body.soul_md_version,
    )


@app.get("/api/v1/installed", dependencies=[Depends(require_operator)])
def list_installed():
    """Operator dashboard: who is running what."""
    return {
        "ok": True,
        "users": manifest_store.list_installed_versions(DB_PATH),
    }


# ─── Root ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "hermes-dist-relay",
        "version": "0.2.0",
        "endpoints": [
            "GET  /api/v1/healthz",
            "POST /api/v1/register",
            "POST /api/v1/submit (HMAC)",
            "GET  /api/v1/manifest?uuid=... (HMAC)",
            "POST /api/v1/heartbeat-ack (HMAC)",
            "POST /api/v1/release (operator)",
            "GET  /api/v1/installed (operator)",
            "GET  /api/v1/events (operator)",
            "GET  /api/v1/users  (operator)",
            "GET  /api/v1/audit  (operator)",
            # Scraper pool
            "POST /api/v1/scrape (HMAC, user)",
            "GET  /api/v1/scrape/result/{job_id} (HMAC, user)",
            "GET  /api/v1/scrape/jobs (operator)",
            "POST /api/v1/scrape/slot/cookies (HMAC, user)",
            # Peer memory
            "POST /api/v1/peer/share (HMAC, owner)",
            "GET  /api/v1/peer/recall (HMAC, anyone)",
            "POST /api/v1/peer/unshare (HMAC, owner)",
            "GET  /api/v1/peer/list (operator)",
        ],
    }


# ─── Scraper pool endpoints ───────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    target_url: str = Field(..., min_length=1, max_length=2048)
    persona_id: str = Field(..., min_length=1, max_length=64)
    method: str = Field("GET", max_length=8)
    body: Optional[str] = None
    headers: Optional[dict] = None
    wait_for: Optional[str] = None
    proxy_url: Optional[str] = None  # user can BYO; operator-pool used if None


class ScrapeSubmitResponse(BaseModel):
    ok: bool
    job_id: str
    slot_id: str
    status: str
    queued_at: str


class ScrapeResultResponse(BaseModel):
    ok: bool
    job_id: str
    status: str
    target_url: str
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    parsed: Optional[dict] = None
    cookies_seen: Optional[list[str]] = None
    scraped_at: Optional[str] = None
    duration_ms: Optional[int] = None
    data_origin: str = "relay_passive_scrape"


class ScrapeCookiesRequest(BaseModel):
    persona_id: str = Field(..., min_length=1, max_length=64)
    cookies: dict


@app.post("/api/v1/scrape", response_model=ScrapeSubmitResponse)
async def submit_scrape(
    body: ScrapeRequest,
    verified: dict = Depends(verify_hmac_request),
):
    """
    User submits a scrape request via their hermes. Routed to a slot keyed
    on (user_uuid, persona_id). Each slot has its own Camofox session, its
    own cookies, and its own proxy. Result lands in scrape_results with
    data_origin='relay_passive_scrape'.
    """
    slot = await _SCRAPER_POOL.get_or_create(
        verified["user_uuid"], body.persona_id, proxy_url=body.proxy_url
    )

    # Body: if string, encode as bytes; if None, NULL
    body_bytes = body.body.encode("utf-8") if body.body else None

    job_id = scraper_jobs.create_job(
        user_uuid=verified["user_uuid"],
        persona_id=body.persona_id,
        target_url=body.target_url,
        method=body.method,
        body=body_bytes,
        headers=body.headers,
        wait_for=body.wait_for,
        db_path=SCRAPER_DB_PATH,
    )

    sqlite_store.audit(
        DB_PATH, verified["user_uuid"], "scrape_queued", job_id,
        f"slot={slot.slot_id} url={body.target_url[:128]}"
    )

    # TODO: dispatch to actual Playwright worker pool
    # For now: mark as running and queued for a (not-yet-existing) worker.
    # When the worker is implemented, it will:
    #   1. claim the job (status=queued -> running)
    #   2. use slot.cookies_path + slot.fingerprint_path to load Camofox
    #   3. navigate to body.target_url
    #   4. wait_for body.wait_for if provided
    #   5. capture HTML, cookies_seen, status_code, final_url
    #   6. write to scrape_results
    #   7. mark job status=done or failed
    scraper_jobs.update_job_status(job_id, "running", db_path=SCRAPER_DB_PATH)

    return ScrapeSubmitResponse(
        ok=True,
        job_id=job_id,
        slot_id=slot.slot_id,
        status="running",
        queued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@app.get("/api/v1/scrape/result/{job_id}", response_model=ScrapeResultResponse)
async def get_scrape_result(
    job_id: str,
    verified: dict = Depends(verify_hmac_request),
):
    """
    User polls for the result of a scrape job they submitted.
    Returns preview of metadata + parsed JSON; raw_html is NOT returned
    over the wire (too big; user retrieves it via a separate signed URL).
    """
    result = scraper_jobs.get_result(job_id, SCRAPER_DB_PATH)
    if not result:
        # Job exists but result not yet; return status
        job = scraper_jobs.get_job(job_id, SCRAPER_DB_PATH)
        if not job:
            raise HTTPException(404, "job not found")
        return ScrapeResultResponse(
            ok=True, job_id=job_id, status=job["status"], target_url=job["target_url"]
        )

    # Privacy: only the owner can read their own scrape results
    if result["user_uuid"] != verified["user_uuid"]:
        raise HTTPException(403, "not your job")

    return ScrapeResultResponse(
        ok=True,
        job_id=result["job_id"],
        status="done",
        target_url=result["target_url"],
        status_code=result["status_code"],
        final_url=result["final_url"],
        parsed=result["parsed"],
        cookies_seen=result["cookies_seen"],
        scraped_at=result["scraped_at"],
        duration_ms=result["duration_ms"],
        data_origin=result["data_origin"],
    )


@app.post("/api/v1/scrape/slot/cookies")
async def set_slot_cookies(
    body: ScrapeCookiesRequest,
    verified: dict = Depends(verify_hmac_request),
):
    """User injects auth cookies for a slot (e.g., Reddit login)."""
    ok = await _SCRAPER_POOL.set_cookies(
        verified["user_uuid"], body.persona_id, body.cookies
    )
    if not ok:
        # Create the slot on demand
        await _SCRAPER_POOL.get_or_create(verified["user_uuid"], body.persona_id)
        ok = await _SCRAPER_POOL.set_cookies(
            verified["user_uuid"], body.persona_id, body.cookies
        )
    sqlite_store.audit(DB_PATH, verified["user_uuid"], "slot_cookies_set",
                       body.persona_id,
                       f"cookies={len(body.cookies)}")
    return {"ok": ok}


@app.get("/api/v1/scrape/jobs", dependencies=[Depends(require_operator)])
def list_scraper_jobs(limit: int = 100):
    """Operator dashboard: active scraper slots."""
    return {
        "ok": True,
        "pool_stats": _SCRAPER_POOL.stats(),
    }


# ─── Peer memory endpoints (preview-only) ─────────────────────────────────

class PeerShareRequest(BaseModel):
    memory_id: str = Field(..., min_length=1, max_length=64)
    preview: str = Field(..., min_length=1, max_length=2048)  # server-side truncates to 280
    source: str = Field(..., min_length=1, max_length=16)
    persona_id: Optional[str] = Field(None, max_length=64)
    tags: Optional[list[str]] = None
    reliability: str = Field("raw_unverified", max_length=16)
    origin_kind: str = Field("peer_relay", max_length=16)


class PeerRecallResponse(BaseModel):
    ok: bool
    count: int
    items: list[dict]
    _preview_only: bool = True


class PeerUnshareRequest(BaseModel):
    memory_id: str = Field(..., min_length=1, max_length=64)


@app.post("/api/v1/peer/share")
async def peer_share(
    body: PeerShareRequest,
    verified: dict = Depends(verify_hmac_request),
):
    """
    Owner shares a memory preview to the group. Preview is truncated
    server-side to 280 chars; full content is NEVER sent to the relay.
    """
    try:
        result = peer_index.share_memory(
            memory_id=body.memory_id,
            owner_user_uuid=verified["user_uuid"],
            preview=body.preview,
            source=body.source,
            owner_persona=body.persona_id,
            tags=body.tags or [],
            reliability=body.reliability,
            origin_kind=body.origin_kind,
            db_path=PEER_DB_PATH,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    sqlite_store.audit(DB_PATH, verified["user_uuid"], "peer_shared",
                       body.memory_id, f"persona={body.persona_id or '?'}")
    return {"ok": True, **result}


@app.post("/api/v1/peer/unshare")
async def peer_unshare(
    body: PeerUnshareRequest,
    verified: dict = Depends(verify_hmac_request),
):
    ok = peer_index.unshare_memory(
        body.memory_id, verified["user_uuid"], PEER_DB_PATH
    )
    if ok:
        sqlite_store.audit(DB_PATH, verified["user_uuid"], "peer_unshared",
                           body.memory_id, "")
    return {"ok": ok}


@app.get("/api/v1/peer/recall", response_model=PeerRecallResponse)
async def peer_recall(
    owner_user_uuid: Optional[str] = None,
    tags: Optional[str] = None,  # comma-separated
    since: Optional[str] = None,
    limit: int = 50,
    verified: dict = Depends(verify_hmac_request),
):
    """Any user pulls preview-only entries from the group index."""
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    items = peer_index.recall_previews(
        owner_user_uuid=owner_user_uuid,
        tags=tag_list or None,
        since=since,
        limit=min(limit, 200),
        db_path=PEER_DB_PATH,
    )
    return PeerRecallResponse(ok=True, count=len(items), items=items)


@app.get("/api/v1/peer/list", dependencies=[Depends(require_operator)])
def peer_list(limit: int = 100):
    """Operator dashboard: what has been shared across the group."""
    items = peer_index.recall_previews(limit=min(limit, 500), db_path=PEER_DB_PATH)
    return {"ok": True, "count": len(items), "items": items}


# ─── Mount dashboard router ──────────────────────────────────────────────

app.include_router(dashboard_router.router)
