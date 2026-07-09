# Hermes-Dist Operator Dashboard
#
# Minimal HTML/JSON views for the operator to inspect what's happening
# across the small-group hermes-dist install.
#
# Mounted at /dashboard/* by main.py. Auth = same X-Operator-Token header
# as the JSON endpoints, but checked here with a small cookie-based session
# so the operator doesn't have to paste the token on every page load.
#
# Endpoints:
#   GET  /dashboard/                 index (overview)
#   GET  /dashboard/login            login form
#   POST /dashboard/login            accept token, set cookie, redirect
#   GET  /dashboard/installed        users and their installed versions
#   GET  /dashboard/events           recent signed events
#   GET  /dashboard/audit            audit log
#   GET  /dashboard/scrape           scraper pool status
#   GET  /dashboard/peer             peer index (operator view)
#   GET  /dashboard/release          release / publish form

import hmac
import html
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# DB_PATH / OPERATOR_TOKEN / SCRAPER_DB_PATH / PEER_DB_PATH / DB_PATH are
# looked up from env at module import time, so this module must be loaded
# AFTER the env vars are set in main.py.

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SESSION_COOKIE = "hermes_dist_dashboard"
SESSION_SECRET = os.environ.get("DASHBOARD_SESSION_SECRET", os.urandom(32).hex())


def _check_token(token: str) -> bool:
    """Constant-time compare against the operator token from env."""
    expected = os.environ.get("OPERATOR_TOKEN", "")
    if not expected or len(token) != 64:
        return False
    return hmac.compare_digest(token, expected)


def require_session(request: Request) -> bool:
    cookie = request.cookies.get(SESSION_COOKIE, "")
    if not cookie or ":" not in cookie:
        return False
    timestamp_hex, signature_hex = cookie.split(":", 1)
    try:
        timestamp = int(timestamp_hex, 16)
        from datetime import datetime, timezone
        age = abs((datetime.now(timezone.utc).timestamp() - timestamp))
        if age > 86400:  # 24h
            return False
    except ValueError:
        return False
    expected_sig = hmac.new(SESSION_SECRET.encode(),
                            timestamp_hex.encode(),
                            "sha256").hexdigest()
    return hmac.compare_digest(expected_sig, signature_hex)


def make_session_cookie() -> str:
    import time as _time
    timestamp = int(_time.time())
    timestamp_hex = format(timestamp, "x")
    sig = hmac.new(SESSION_SECRET.encode(),
                   timestamp_hex.encode(),
                   "sha256").hexdigest()
    return f"{timestamp_hex}:{sig}"


# ─── Pages ──────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse("login.html", {
        "request": request, "error": error,
    })


@router.post("/login")
def login_submit(request: Request, token: str = Form(...)):
    if not _check_token(token):
        return RedirectResponse("/dashboard/login?error=invalid", status_code=303)
    resp = RedirectResponse("/dashboard/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, make_session_cookie(),
                    httponly=True, samesite="strict", max_age=86400)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/dashboard/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.get("/", response_class=HTMLResponse)
def dashboard_index(request: Request):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    # Lazy import — these modules set up DBs at import-time; we don't want
    # to trigger that at module load.
    from . import sqlite_store, manifest_store, scraper_jobs, peer_index

    db_path = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
    scraper_db = Path(os.environ.get("SCRAPER_DB_PATH", "/var/lib/hermes-relay/scraper.db"))
    peer_db = Path(os.environ.get("PEER_DB_PATH", "/var/lib/hermes-relay/peer_index.db"))

    with sqlite_store.get_conn(db_path) as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    installed = manifest_store.list_installed_versions(db_path)
    peer_count = len(peer_index.recall_previews(limit=500, db_path=peer_db))

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_count": user_count,
        "event_count": event_count,
        "installed_count": len(installed),
        "peer_count": peer_count,
    })


@router.get("/installed", response_class=HTMLResponse)
def dashboard_installed(request: Request):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    from . import manifest_store
    db_path = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
    installed = manifest_store.list_installed_versions(db_path)
    return templates.TemplateResponse("installed.html", {
        "request": request, "users": installed,
    })


@router.get("/events", response_class=HTMLResponse)
def dashboard_events(request: Request, limit: int = 50):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    from . import sqlite_store
    db_path = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
    events = sqlite_store.list_events(limit=min(limit, 200), db_path=db_path)
    return templates.TemplateResponse("events.html", {
        "request": request, "events": events, "limit": limit,
    })


@router.get("/audit", response_class=HTMLResponse)
def dashboard_audit(request: Request, limit: int = 100):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    from . import sqlite_store
    db_path = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
    entries = sqlite_store.list_audit(limit=min(limit, 500), db_path=db_path)
    return templates.TemplateResponse("audit.html", {
        "request": request, "entries": entries, "limit": limit,
    })


@router.get("/scrape", response_class=HTMLResponse)
def dashboard_scrape(request: Request):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    from .scraper_router import ScraperPool
    from pathlib import Path
    slot_root = Path(os.environ.get("SCRAPER_SLOT_ROOT", "/var/lib/hermes-relay/scraper-slots"))
    pool = ScraperPool(slot_root=slot_root)
    stats = pool.stats()
    return templates.TemplateResponse("scrape.html", {
        "request": request, "stats": stats,
    })


@router.get("/peer", response_class=HTMLResponse)
def dashboard_peer(request: Request, limit: int = 50):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    from . import peer_index
    db_path = Path(os.environ.get("PEER_DB_PATH", "/var/lib/hermes-relay/peer_index.db"))
    items = peer_index.recall_previews(limit=min(limit, 200), db_path=db_path)
    return templates.TemplateResponse("peer.html", {
        "request": request, "items": items, "limit": limit,
    })


@router.get("/release", response_class=HTMLResponse)
def dashboard_release_form(request: Request, message: Optional[str] = None):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return templates.TemplateResponse("release.html", {
        "request": request, "message": message,
    })


@router.post("/release")
def dashboard_release_post(
    request: Request,
    soul_md_version: str = Form(...),
    config_yaml_version: str = Form(...),
    hermes_version: str = Form("0.4.2"),
    rollout_pct: int = Form(100),
    message: str = Form(""),
):
    if not require_session(request):
        return RedirectResponse("/dashboard/login", status_code=303)

    soul_md_path = Path(os.environ.get(
        "SOUL_MD_PATH",
        str(Path.home() / "hermes-dist" / "default-template" / "SOUL.md")))
    cfg_path = Path(os.environ.get(
        "CONFIG_YAML_PATH",
        str(Path.home() / "hermes-dist" / "default-template" / "config.yaml")))

    if not soul_md_path.exists() or not cfg_path.exists():
        return RedirectResponse(
            f"/dashboard/release?message=BUNDLE_NOT_FOUND:{soul_md_path}",
            status_code=303)

    soul_md = soul_md_path.read_text(encoding="utf-8")
    cfg_yaml = cfg_path.read_text(encoding="utf-8")

    from . import manifest_store, sqlite_store
    db_path = Path(os.environ.get("RELAY_DB_PATH", "/var/lib/hermes-relay/relay.db"))
    try:
        version_id = manifest_store.publish_manifest(
            soul_md_version=soul_md_version,
            config_yaml_version=config_yaml_version,
            hermes_version=hermes_version,
            soul_md_content=soul_md,
            config_yaml_content=cfg_yaml,
            released_by=os.environ.get("OPERATOR_NAME", "operator"),
            rollout_pct=rollout_pct,
            message=message,
            db_path=db_path,
        )
        sqlite_store.audit(db_path, "_operator", "release_published_dashboard",
                           str(version_id),
                           f"version={soul_md_version} rollout={rollout_pct}%")
    except Exception as e:
        return RedirectResponse(
            f"/dashboard/release?message=ERROR:{html.escape(str(e))}",
            status_code=303)

    return RedirectResponse(
        f"/dashboard/release?message=PUBLISHED:{soul_md_version}",
        status_code=303)


# ─── Helper: HTML escape for any user-supplied data ─────────────────────

def e(s) -> str:
    """Tiny shortcut for Jinja's autoescape edge cases."""
    if s is None:
        return ""
    return html.escape(str(s))