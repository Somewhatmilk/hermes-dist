"""
scraper_jobs.py — SQLite storage for scraper pool jobs and results.

Schema:
  scrape_jobs (
    job_id TEXT PRIMARY KEY,
    user_uuid TEXT NOT NULL,
    persona_id TEXT NOT NULL,        -- which persona of the user requested
    slot_id TEXT NOT NULL,           -- computed (user_uuid, persona_id) -> "u_xxx__p_yyy"
    target_url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'GET',
    body BLOB,
    headers JSON,                    -- extra headers (User-Agent etc.)
    wait_for TEXT,                   -- CSS selector to wait for before capturing
    status TEXT NOT NULL DEFAULT 'queued',  -- queued / running / done / failed
    started_at TEXT,
    finished_at TEXT,
    error TEXT,
    proxy_used TEXT,
    fingerprint_used TEXT,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid)
  )

  scrape_results (
    job_id TEXT PRIMARY KEY,
    user_uuid TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    target_url TEXT NOT NULL,
    status_code INTEGER,
    final_url TEXT,                  -- after redirects
    raw_html BLOB,                   -- full body
    parsed JSON,                     -- optional structured extract
    cookies_seen JSON,               -- cookie names only (audit), not values
    screenshot_path TEXT,            -- if browser used
    scraped_at TEXT NOT NULL,
    duration_ms INTEGER,
    data_origin TEXT NOT NULL DEFAULT 'relay_passive_scrape'
    -- ↑ single hardcoded source for everything relay-scraped
  )

Index: (user_uuid, persona_id, scraped_at DESC) — primary access pattern.

Note: scrape_results holds RAW HTML. Privacy boundary: this is the relay's
DB; it never crosses into a user's Mnemosyne. When a user wants a result,
the relay returns it over HMAC-signed channel and the user's hermes ingests
with source='external', origin_kind='scrape', origin_persona=<slot_id>.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


def get_conn(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_scraper_db(db_path: Path):
    with get_conn(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS scrape_jobs (
            job_id TEXT PRIMARY KEY,
            user_uuid TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            slot_id TEXT NOT NULL,
            target_url TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            body BLOB,
            headers_json TEXT,
            wait_for TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            started_at TEXT,
            finished_at TEXT,
            error TEXT,
            proxy_used TEXT,
            fingerprint_used TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_uuid, persona_id, slot_id)
        );

        CREATE TABLE IF NOT EXISTS scrape_results (
            job_id TEXT PRIMARY KEY,
            user_uuid TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            target_url TEXT NOT NULL,
            status_code INTEGER,
            final_url TEXT,
            raw_html BLOB,
            parsed_json TEXT,
            cookies_seen_json TEXT,
            screenshot_path TEXT,
            scraped_at TEXT NOT NULL,
            duration_ms INTEGER,
            data_origin TEXT NOT NULL DEFAULT 'relay_passive_scrape'
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_user_persona_time
            ON scrape_jobs(user_uuid, persona_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_results_user_persona_time
            ON scrape_results(user_uuid, persona_id, scraped_at DESC);
        """)


def make_slot_id(user_uuid: str, persona_id: str) -> str:
    """Deterministic slot id from (user, persona). Safe filename component."""
    return f"u_{user_uuid[:8].lower()}__p_{persona_id}"


def create_job(user_uuid: str, persona_id: str, target_url: str,
               method: str = "GET", body: bytes | None = None,
               headers: dict | None = None, wait_for: str | None = None,
               db_path: Path = None) -> str:
    """Insert a queued job. Returns the job_id."""
    job_id = str(uuid.uuid4())
    slot_id = make_slot_id(user_uuid, persona_id)
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT INTO scrape_jobs
               (job_id, user_uuid, persona_id, slot_id, target_url, method,
                body, headers_json, wait_for, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?)""",
            (job_id, user_uuid, persona_id, slot_id, target_url, method,
             body, json.dumps(headers) if headers else None, wait_for, created_at),
        )
    return job_id


def get_job(job_id: str, db_path: Path) -> dict | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM scrape_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    return _row_to_job(row)


def _row_to_job(row) -> dict:
    return {
        "job_id": row[0],
        "user_uuid": row[1],
        "persona_id": row[2],
        "slot_id": row[3],
        "target_url": row[4],
        "method": row[5],
        "body": row[6],
        "headers": json.loads(row[7]) if row[7] else None,
        "wait_for": row[8],
        "status": row[9],
        "started_at": row[10],
        "finished_at": row[11],
        "error": row[12],
        "proxy_used": row[13],
        "fingerprint_used": row[14],
        "created_at": row[15],
    }


def update_job_status(job_id: str, status: str, error: str | None = None,
                      proxy_used: str | None = None,
                      fingerprint_used: str | None = None,
                      db_path: Path = None):
    """Mark a job running / done / failed. Audit fields populated here."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fields = {"status": status}
    params = [status]
    if status == "running":
        fields["started_at"] = now
        params.append(now)
    elif status in ("done", "failed"):
        fields["finished_at"] = now
        params.append(now)
    if error is not None:
        fields["error"] = error
        params.append(error)
    if proxy_used is not None:
        fields["proxy_used"] = proxy_used
        params.append(proxy_used)
    if fingerprint_used is not None:
        fields["fingerprint_used"] = fingerprint_used
        params.append(fingerprint_used)
    sets = ", ".join(f"{k} = ?" for k in fields.keys())
    params.append(job_id)
    with get_conn(db_path) as conn:
        conn.execute(
            f"UPDATE scrape_jobs SET {sets} WHERE job_id = ?",
            params,
        )


def store_result(job_id: str, user_uuid: str, persona_id: str,
                 target_url: str, status_code: int | None,
                 final_url: str | None, raw_html: bytes | None,
                 parsed: dict | None, cookies_seen: list[str] | None,
                 screenshot_path: str | None, duration_ms: int,
                 db_path: Path):
    scraped_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO scrape_results
               (job_id, user_uuid, persona_id, target_url, status_code,
                final_url, raw_html, parsed_json, cookies_seen_json,
                screenshot_path, scraped_at, duration_ms, data_origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'relay_passive_scrape')""",
            (job_id, user_uuid, persona_id, target_url, status_code,
             final_url, raw_html,
             json.dumps(parsed) if parsed else None,
             json.dumps(cookies_seen) if cookies_seen else None,
             screenshot_path, scraped_at, duration_ms),
        )


def list_recent_results(user_uuid: str, persona_id: str | None,
                        limit: int = 50, db_path: Path = None) -> list[dict]:
    """Operator dashboard / user query — recent scrape results for a user."""
    if persona_id:
        sql = """SELECT job_id, target_url, status_code, final_url,
                        scraped_at, duration_ms, screenshot_path
                 FROM scrape_results
                 WHERE user_uuid = ? AND persona_id = ?
                 ORDER BY scraped_at DESC LIMIT ?"""
        params = (user_uuid, persona_id, limit)
    else:
        sql = """SELECT job_id, target_url, status_code, final_url,
                        scraped_at, duration_ms, screenshot_path, persona_id
                 FROM scrape_results
                 WHERE user_uuid = ?
                 ORDER BY scraped_at DESC LIMIT ?"""
        params = (user_uuid, limit)
    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    cols = ["job_id", "target_url", "status_code", "final_url",
            "scraped_at", "duration_ms", "screenshot_path"]
    if not persona_id:
        cols.append("persona_id")
    return [dict(zip(cols, r)) for r in rows]


def get_result(job_id: str, db_path: Path) -> dict | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """SELECT job_id, user_uuid, persona_id, target_url, status_code,
                      final_url, raw_html, parsed_json, cookies_seen_json,
                      screenshot_path, scraped_at, duration_ms
               FROM scrape_results WHERE job_id = ?""",
            (job_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "job_id": row[0],
        "user_uuid": row[1],
        "persona_id": row[2],
        "target_url": row[3],
        "status_code": row[4],
        "final_url": row[5],
        "raw_html": row[6],
        "parsed": json.loads(row[7]) if row[7] else None,
        "cookies_seen": json.loads(row[8]) if row[8] else None,
        "screenshot_path": row[9],
        "scraped_at": row[10],
        "duration_ms": row[11],
        "data_origin": "relay_passive_scrape",
    }