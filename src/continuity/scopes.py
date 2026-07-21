"""Typed contracts for canonical identities and Hermes session lineage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IdentityKind(StrEnum):
    USER = "user"
    AGENT = "agent"
    WORKSPACE = "workspace"
    PLATFORM_USER = "platform_user"


class LineageReason(StrEnum):
    NEW = "new"
    RESET = "reset"
    RESUME = "resume"
    BRANCH = "branch"
    COMPRESSION = "compression"
    REWIND = "rewind"


class IdentityRef(BaseModel):
    """A canonical identity plus an optional external alias to link."""

    model_config = ConfigDict(extra="forbid")

    kind: IdentityKind
    canonical_key: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    source_system: str | None = Field(default=None, max_length=100)
    external_type: str | None = Field(default=None, max_length=100)
    external_id: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("canonical_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_external_link(self) -> "IdentityRef":
        supplied = [self.source_system, self.external_type, self.external_id]
        if any(supplied) and not all(supplied):
            raise ValueError(
                "source_system, external_type, and external_id must be supplied together"
            )
        return self


class IdentityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    kind: IdentityKind
    canonical_key: str
    display_name: str | None = None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    linked: bool = False


class SessionOpen(BaseModel):
    """Open or resolve a Hermes session and its canonical scopes."""

    model_config = ConfigDict(extra="forbid")

    external_session_id: str = Field(min_length=1, max_length=512)
    source_system: str = Field(default="hermes", min_length=2, max_length=100)
    platform: str | None = Field(default=None, max_length=100)
    lineage_reason: LineageReason = LineageReason.NEW
    parent_external_session_id: str | None = Field(default=None, max_length=512)
    user: IdentityRef | None = None
    agent: IdentityRef | None = None
    workspace: IdentityRef | None = None
    project_id: UUID | None = None
    task_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_parent_for_lineage(self) -> "SessionOpen":
        if self.lineage_reason in {
            LineageReason.RESUME,
            LineageReason.BRANCH,
            LineageReason.COMPRESSION,
        } and not self.parent_external_session_id:
            raise ValueError(
                f"parent_external_session_id is required for {self.lineage_reason.value}"
            )
        return self


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    external_session_id: str
    source_system: str
    user_identity_id: UUID | None = None
    agent_identity_id: UUID | None = None
    workspace_identity_id: UUID | None = None
    project_id: UUID | None = None
    task_id: UUID | None = None
    parent_session_id: UUID | None = None
    lineage_reason: LineageReason | None = None
    platform: str | None = None
    status: str
    summary: str | None = None
    metadata: dict[str, Any]
    started_at: datetime
    ended_at: datetime | None = None
    duplicate: bool = False
