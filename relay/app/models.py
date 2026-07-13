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


# ─── T3: profile bundles (push updates) ───────────────────────────────────

class ProfileBundlePublishRequest(BaseModel):
    """
    Body of POST /api/v1/profile-bundle (operator auth).

    `released_at` is an ISO 8601 UTC timestamp. We accept both the ISO
    string (preferred, human-readable in audit) AND derive a unix-ts for
    the DB index. The `version` field is the dedup key — republishing
    the same version is a no-op (returns 200 with `inserted=False`).
    """
    soul_md: str = Field(..., min_length=0, max_length=1_000_000)
    config_yaml: str = Field(..., min_length=0, max_length=1_000_000)
    toolsets_json: str = Field(..., min_length=0, max_length=1_000_000)
    version: str = Field(..., min_length=1, max_length=64)
    released_at: str = Field(..., min_length=20, max_length=32)


class ProfileBundlePublishResponse(BaseModel):
    ok: bool
    inserted: bool             # True if new row, False if version was already present
    bundle_id: int
    version: str
    released_at_unix: int
    released_at_iso: str
    published_at: str          # when the relay recorded the publish
    bytes_total: int


class ProfileBundleFetchResponse(BaseModel):
    """
    Body of GET /api/v1/profile-bundle?since=<unix_ts> (user HMAC auth).

    `up_to_date: true` means the client already has the latest bundle
    (nothing returned since `since`). `up_to_date: false` means a newer
    bundle exists and its full payload is in `bundle`.
    """
    ok: bool
    up_to_date: bool
    server_time_unix: int
    since_unix: int
    bundle: Optional["ProfileBundlePayload"] = None


class ProfileBundlePayload(BaseModel):
    bundle_id: int
    version: str
    released_at_unix: int
    released_at_iso: str
    soul_md: str
    config_yaml: str
    toolsets_json: str
    bytes_total: int
    published_at: str


class ProfileBundleListResponse(BaseModel):
    """Operator-only metadata listing (no body content)."""
    ok: bool
    count: int
    bundles: list[dict]


# ─── T13: Multi-tenant hub JSON-RPC (v0.5.0) ─────────────────────────────

class SkillListResponse(BaseModel):
    """Body of GET /api/v1/skills."""
    ok: bool
    skills: list[dict] = Field(default_factory=list)
    count: int


class SkillReadResponse(BaseModel):
    """Body of GET /api/v1/skills/<name>."""
    ok: bool
    name: Optional[str] = None
    path: Optional[str] = None
    content: Optional[str] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None


class ToolInvokeRequest(BaseModel):
    """Body of POST /api/v1/tools/invoke."""
    tool: str = Field(..., min_length=1, max_length=128)
    args: dict = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Body of POST /api/v1/tools/invoke response."""
    ok: bool
    tool: Optional[str] = None
    output: Optional[Any] = None
    scope_used: Optional[str] = None
    audit_id: Optional[int] = None
    error: Optional[str] = None


class DockerRunRequest(BaseModel):
    """Body of POST /api/v1/docker/run."""
    image: str = Field(..., min_length=1, max_length=256)
    cmd: list[str] = Field(..., min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    mounts: list[dict] = Field(default_factory=list)


class DockerRunResponse(BaseModel):
    """Body of POST /api/v1/docker/run response."""
    ok: bool
    stub: bool = False
    message: Optional[str] = None
    would_run: Optional[dict] = None
    error: Optional[str] = None
