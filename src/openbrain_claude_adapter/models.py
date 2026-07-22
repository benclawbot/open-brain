"""Typed configuration for a Claude Code/Open Brain session bridge."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.providers import ProviderScope


class ClaudeSessionContext(BaseModel):
    """Stable host-supplied identifiers for one Claude Code session."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    session_key: str = Field(min_length=1, max_length=512)
    workspace_path: Path
    client_version: str = Field(default="unknown", min_length=1, max_length=100)
    scope: ProviderScope = Field(default_factory=ProviderScope)
