"""Typed Medusa-to-Open-Brain lifecycle models."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.providers import ProviderScope


class MedusaSessionContext(BaseModel):
    """Stable identity and local durability settings for one Medusa session."""

    model_config = ConfigDict(extra="forbid")

    session_key: str = Field(min_length=1, max_length=512)
    workspace_path: Path
    scope: ProviderScope = Field(default_factory=ProviderScope)
    agent_version: str = Field(default="unknown", min_length=1, max_length=64)
    spool_path: Path | None = None

    def effective_spool_path(self) -> Path:
        return self.spool_path or self.workspace_path / ".medusa" / "openbrain-spool.jsonl"


class RecallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_id: UUID | None = None
    prompt_block: str = ""
    item_count: int = 0
    unavailable: bool = False
