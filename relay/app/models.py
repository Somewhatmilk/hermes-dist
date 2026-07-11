"""
Pydantic models for relay API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class RegisterRequest(BaseModel):
    uuid: str = Field(..., min_length=32, max_length=64)
    os: str = Field(..., max_length=64)
    version: str = Field(..., max_length=64)
    opted_in: bool
    registered_at: str = Field(..., max_length=32)


class RegisterResponse(BaseModel):
    ok: bool
    registered: bool
    hmac_secret: Optional[str] = None  # only returned on first registration
    relay_version: str = "hermes-relay-0.1.0"


class SubmitResponse(BaseModel):
    ok: bool
    event_id: int
    received_at: str
    # T9: which dedup layer ran for this event.
    #   "inserted"      — fresh row written
    #   "deduped_b"     — Layer B (content-hash, 24h) bumped an existing row
    #   "coalesced_c"   — Layer C (tool_invocation argv, 30s) coalesced into
    #                      an existing row
    dedup: str = "inserted"
    dedup_count: int = 1
    coalesced_count: int = 1


class EventsResponse(BaseModel):
    ok: bool
    count: int
    events: list[dict]


class UsersResponse(BaseModel):
    ok: bool
    count: int
    users: list[dict]


class HealthResponse(BaseModel):
    ok: bool
    version: str
    uptime_seconds: float
    db_size_mb: float
    user_count: int
    event_count: int


class StorageBucket(BaseModel):
    total: int
    by_type: dict[str, int] = Field(default_factory=dict)


class StorageStatsResponse(BaseModel):
    """Operator-facing storage stats (T10)."""
    events: StorageBucket
    events_archive: StorageBucket
    eligible_for_archive_now: int
    db_size_bytes: int
    db_size_mb: float
    retention_policy_days: dict[str, Optional[int]] = Field(default_factory=dict)
    default_retention_days: int
    next_archive_run_local: str
