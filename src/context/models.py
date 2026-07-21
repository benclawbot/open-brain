"""Contracts for compact, revision-aware context delivery to agents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrustLabel(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    TOOL_OBSERVED = "tool_observed"
    CURATED_MEMORY = "curated_memory"
    INFERRED = "inferred"
    STALE = "stale"
    CONTRADICTED = "contradicted"


class ContextKind(StrEnum):
    PROJECT = "project"
    TASK = "task"
    DECISION = "decision"
    ASSERTION = "assertion"
    OUTCOME = "outcome"
    WARNING = "warning"
    NEXT_ACTION = "next_action"


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | str
    kind: ContextKind
    text: str = Field(min_length=1, max_length=20000)
    trust: TrustLabel
    importance: float = Field(default=0.5, ge=0, le=1)
    observed_at: datetime | None = None
    stale: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_identity_id: UUID | None = None
    project_id: UUID | None = None
    task_id: UUID | None = None
    max_items: int = Field(default=20, ge=1, le=100)
    token_budget: int = Field(default=1600, ge=128, le=12000)
    include_history: bool = False


class ContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: UUID
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope_revisions: dict[str, int]
    items: list[ContextItem]
    estimated_tokens: int
    truncated: bool = False


class FeedbackDisposition(StrEnum):
    USED = "used"
    IRRELEVANT = "irrelevant"
    INCORRECT = "incorrect"
    MISSING = "missing"


class ContextFeedbackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_item_id: UUID | str
    disposition: FeedbackDisposition
    note: str | None = Field(default=None, max_length=5000)


class ContextFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: UUID
    items: list[ContextFeedbackItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    outcome: str | None = Field(default=None, max_length=100)
