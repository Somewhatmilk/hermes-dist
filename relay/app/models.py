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
