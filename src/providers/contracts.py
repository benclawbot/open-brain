"""Stable contracts for coding-agent integrations.

The provider SDK deliberately stays transport-agnostic. Agent adapters translate
native lifecycle events into these models, while :mod:`src.providers.client`
handles Open Brain REST transport.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.continuity.models import Sensitivity, TrustAuthority


class ProviderCapability(StrEnum):
    """Optional integration features an adapter can expose."""

    RECALL = "recall"
    REMEMBER = "remember"
    SESSION_LIFECYCLE = "session_lifecycle"
    TOOL_EVENTS = "tool_events"
    DELEGATION = "delegation"
    COMPRESSION = "compression"
    OFFLINE_SPOOL = "offline_spool"


class ProviderDescriptor(BaseModel):
    """Machine-readable metadata for one agent adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=64)
    capabilities: frozenset[ProviderCapability] = Field(default_factory=frozenset)


class ProviderScope(BaseModel):
    """Canonical Open Brain scope passed by an agent integration."""

    model_config = ConfigDict(extra="forbid")

    user_identity_id: UUID | None = None
    agent_identity_id: UUID | None = None
    workspace_identity_id: UUID | None = None
    session_id: UUID | None = None
    project_id: UUID | None = None
    task_id: UUID | None = None


class RecallRequest(BaseModel):
    """Request for the server's actionable context packet."""

    model_config = ConfigDict(extra="forbid")

    scope: ProviderScope = Field(default_factory=ProviderScope)
    token_budget: int = Field(default=1600, ge=128, le=12_000)
    max_items: int = Field(default=20, ge=1, le=100)
    include_history: bool = False


class RememberRequest(BaseModel):
    """Normalized provider event accepted by every adapter."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(min_length=3, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=512)
    payload: dict[str, Any]
    scope: ProviderScope = Field(default_factory=ProviderScope)
    source_record_id: str | None = Field(default=None, max_length=512)
    authority: TrustAuthority = TrustAuthority.PROVIDER_INFERENCE
    sensitivity: Sensitivity = Sensitivity.NORMAL
    retention_policy: str = Field(default="default", min_length=1, max_length=100)


@runtime_checkable
class MemoryProvider(Protocol):
    """Minimal adapter contract for coding agents and gateways."""

    descriptor: ProviderDescriptor

    def recall(self, request: RecallRequest) -> dict[str, Any]: ...

    def remember(self, request: RememberRequest) -> dict[str, Any]: ...

    def health(self) -> dict[str, Any]: ...

    def close(self) -> None: ...
