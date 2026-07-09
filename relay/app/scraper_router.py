"""
scraper_router.py — per-(user_uuid, persona_id) scraper slot pool.

Each unique (user, persona) pair gets its own slot. A slot owns:
  - Its own Camofox session dir (browser cookies, local storage, fingerprint)
  - Its own cookies.json (auth cookies for the target site)
  - Its own proxy (operator-pool or BYO)
  - Its own rate limit
  - Its own request queue

Slots persist across relay restarts (cookie file lives on disk; pool state
in this file's SQLite is ephemeral, rebuilt on startup).

Privacy boundary:
  - Slot files live on the RELAY host, not the user host.
  - User's hermes never sees the raw cookies.
  - User's hermes calls /api/v1/scrape with their persona_id; gets back a
    job_id; later polls /api/v1/scrape/result/{job_id} for the result.
  - The result lands in user's hermes as source='external', origin_kind='scrape'.
"""
import asyncio
import json
import os
import secrets
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RateLimit:
    requests_per_minute: int = 30
    concurrent: int = 2
    _timestamps: list[float] = field(default_factory=list)
    _semaphore: asyncio.Semaphore = field(default=None)

    def __post_init__(self):
        # asyncio.Semaphore can't be created at __post_init__ because
        # there's no event loop yet. Lazy-init on first await.
        pass


@dataclass
class ScraperSlot:
    slot_id: str
    user_uuid: str
    persona_id: str
    cookies_path: Path
    fingerprint_path: Path
    proxy_url: Optional[str] = None
    rate_limit: RateLimit = field(default_factory=RateLimit)
    last_used_at: float = 0.0
    lock_path: Path = None  # set in __post_init__

    def touch(self):
        self.last_used_at = time.time()


class ScraperPool:
    """
    In-memory slot pool, keyed on (user_uuid, persona_id).

    On startup: scan slot_dir/ for existing session dirs, rebuild the dict.
    On LRU eviction: zero out cookies (privacy), remove session dir.
    On shutdown: just drop the in-memory dict; session dirs persist.
    """

    def __init__(self, slot_root: Path, max_slots: int = 32,
                 idle_evict_seconds: int = 86400):
        self.slot_root = Path(slot_root)
        self.slot_root.mkdir(parents=True, exist_ok=True)
        self.max_slots = max_slots
        self.idle_evict_seconds = idle_evict_seconds
        self._slots: dict[tuple[str, str], ScraperSlot] = {}
        self._lock = asyncio.Lock()
        self._rebuild_from_disk()

    def _rebuild_from_disk(self):
        """Scan slot_root for u_*/p_* dirs and rebuild in-memory index."""
        for path in self.slot_root.iterdir():
            if not path.is_dir():
                continue
            name = path.name
            # name format: u_<uuid8>__p_<persona>
            if not name.startswith("u_") or "__p_" not in name:
                continue
            try:
                u_part, p_part = name.split("__p_", 1)
                u_prefix = u_part[2:]  # strip "u_"
                # we don't have the full uuid, just the prefix; we still
                # need to know the full uuid to route. Solution: store a
                # sidecar file (slot.json) with full uuid + persona.
                meta_path = path / "slot.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    key = (meta["user_uuid"], meta["persona_id"])
                    self._slots[key] = ScraperSlot(
                        slot_id=name,
                        user_uuid=meta["user_uuid"],
                        persona_id=meta["persona_id"],
                        cookies_path=path / "cookies.json",
                        fingerprint_path=path / "fingerprint.json",
                        proxy_url=meta.get("proxy_url"),
                        rate_limit=RateLimit(**meta.get("rate_limit", {})),
                        last_used_at=meta.get("last_used_at", 0.0),
                        lock_path=path / "slot.lock",
                    )
            except (ValueError, KeyError, json.JSONDecodeError):
                # Malformed slot dir — skip
                continue

    def _persist_slot_meta(self, slot: ScraperSlot):
        meta_path = self.slot_root / slot.slot_id / "slot.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({
            "user_uuid": slot.user_uuid,
            "persona_id": slot.persona_id,
            "proxy_url": slot.proxy_url,
            "rate_limit": {
                "requests_per_minute": slot.rate_limit.requests_per_minute,
                "concurrent": slot.rate_limit.concurrent,
            },
            "last_used_at": slot.last_used_at,
        }))

    async def get_or_create(self, user_uuid: str, persona_id: str,
                            proxy_url: Optional[str] = None) -> ScraperSlot:
        async with self._lock:
            key = (user_uuid, persona_id)
            if key in self._slots:
                slot = self._slots[key]
                slot.touch()
                self._persist_slot_meta(slot)
                return slot

            # Evict if at capacity
            if len(self._slots) >= self.max_slots:
                await self._evict_idle()

            slot_id = f"u_{user_uuid[:8].lower()}__p_{persona_id}"
            slot_dir = self.slot_root / slot_id
            slot_dir.mkdir(parents=True, exist_ok=True)
            slot = ScraperSlot(
                slot_id=slot_id,
                user_uuid=user_uuid,
                persona_id=persona_id,
                cookies_path=slot_dir / "cookies.json",
                fingerprint_path=slot_dir / "fingerprint.json",
                proxy_url=proxy_url,
                lock_path=slot_dir / "slot.lock",
            )
            self._slots[key] = slot
            self._persist_slot_meta(slot)
            return slot

    async def _evict_idle(self):
        """Remove slots idle longer than idle_evict_seconds. Privacy: wipe cookies first."""
        now = time.time()
        idle_keys = [
            k for k, s in self._slots.items()
            if (now - s.last_used_at) > self.idle_evict_seconds
        ]
        for key in idle_keys:
            slot = self._slots.pop(key)
            # Privacy: zero out cookies BEFORE removal
            if slot.cookies_path.exists():
                slot.cookies_path.write_text("{}")
            if slot.fingerprint_path.exists():
                slot.fingerprint_path.unlink()
            slot_dir = self.slot_root / slot.slot_id
            if slot_dir.exists():
                shutil.rmtree(slot_dir)

    async def set_proxy(self, user_uuid: str, persona_id: str,
                        proxy_url: Optional[str]):
        async with self._lock:
            key = (user_uuid, persona_id)
            if key not in self._slots:
                return False
            self._slots[key].proxy_url = proxy_url
            self._persist_slot_meta(self._slots[key])
            return True

    async def set_cookies(self, user_uuid: str, persona_id: str,
                          cookies: dict):
        """Operator injects cookies for a slot (e.g., Reddit login)."""
        async with self._lock:
            key = (user_uuid, persona_id)
            if key not in self._slots:
                return False
            slot = self._slots[key]
            slot.cookies_path.write_text(json.dumps(cookies, indent=2))
            slot.cookies_path.chmod(0o600)
            return True

    def stats(self) -> dict:
        return {
            "total_slots": len(self._slots),
            "max_slots": self.max_slots,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "user_uuid": s.user_uuid[:8],
                    "persona_id": s.persona_id,
                    "proxy": s.proxy_url or "(direct)",
                    "last_used": s.last_used_at,
                    "has_cookies": s.cookies_path.exists()
                                  and s.cookies_path.stat().st_size > 2,
                }
                for s in self._slots.values()
            ],
        }


# ─── Per-slot rate limiting (token bucket) ─────────────────────────────────

class TokenBucket:
    """Simple token-bucket rate limiter. Async-safe via asyncio.Lock."""

    def __init__(self, rate_per_minute: int):
        self.capacity = rate_per_minute
        self.tokens = float(rate_per_minute)
        self.refill_rate = rate_per_minute / 60.0  # tokens per second
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            # Need to wait
            deficit = tokens - self.tokens
            wait_seconds = deficit / self.refill_rate
            await asyncio.sleep(wait_seconds)
            self.tokens = 0
            return True