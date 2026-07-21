"""Typed contracts for durable continuity events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrustAuthority(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    TOOL_OBSERVED = "tool_observed"
    CURATED_MEMORY = "curated_memory"
    PROVIDER_INFERENCE = "provider_inference"
    OPENBRAIN_INFERENCE = "openbrain_inference"
    ASSISTANT_CLAIM = "assistant_claim"
    UNKNOWN = "unknown"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class ScopeRef(BaseModel):
    """Canonical scope identifiers associated with an event."""

    model_config = ConfigDict(extra="forbid")

    user_identity_id: UUID | None = None
    agent_identity_id: UUID | None = None
    workspace_identity_id: UUID | None = None
    session_id: UUID | None = None
    project_id: UUID | None = None
    task_id: UUID | None = None


class EventCreate(BaseModel):
    """Input contract used by Hermes and other producers."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(min_length=3, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=512)
    source_system: str = Field(min_length=2, max_length=100)
    source_record_id: str | None = Field(default=None, max_length=512)
    scope: ScopeRef = Field(default_factory=ScopeRef)
    causation_id: UUID | None = None
    correlation_id: UUID | None = None
    authority: TrustAuthority = TrustAuthority.UNKNOWN
    sensitivity: Sensitivity = Sensitivity.NORMAL
    retention_policy: str = Field(default="default", min_length=1, max_length=100)
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "." not in normalized:
            raise ValueError("event_type must be namespaced, for example conversation.user_message")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class EventRecord(BaseModel):
    """Persisted event returned to API clients."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    event_type: str
    idempotency_key: str
    source_system: str
    source_record_id: str | None = None
    scope: ScopeRef
    causation_id: UUID | None = None
    correlation_id: UUID | None = None
    authority: TrustAuthority
    sensitivity: Sensitivity
    retention_policy: str
    payload: dict[str, Any]
    occurred_at: datetime
    ingested_at: datetime
    duplicate: bool = False
