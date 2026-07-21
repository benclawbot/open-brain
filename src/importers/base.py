"""Shared contracts for resumable, provenance-preserving imports."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field


class ImportSource(StrEnum):
    HERMES_USER_MEMORY = "hermes.user_memory"
    HERMES_AGENT_MEMORY = "hermes.agent_memory"
    HERMES_CONTEXT = "hermes.context"
    HERMES_SESSION = "hermes.session"
    HERMES_SKILL = "hermes.skill"
    HERMES_CRON = "hermes.cron"
    MEMORY_PROVIDER = "memory_provider"


class ImportCandidate(BaseModel):
    """Normalized source record awaiting reconciliation and promotion."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=1024)
    external_hash: str = Field(min_length=64, max_length=64)
    source: ImportSource
    content: str = Field(min_length=1)
    record_type: str = Field(min_length=1, max_length=100)
    authority: str = Field(default="unknown", max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


def hash_content(content: str | bytes) -> str:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(payload).hexdigest()


def stable_file_id(path: Path, section: str, ordinal: int) -> str:
    return f"{path.expanduser().resolve()}::{section}::{ordinal}"


class ImportAdapter(ABC):
    """Adapters discover and normalize records without mutating source systems."""

    @abstractmethod
    def discover(self) -> Iterable[ImportCandidate]:
        """Yield normalized candidates in deterministic source order."""

    def source_fingerprint(self) -> str:
        """Hash adapter configuration for safe resume detection."""
        return hash_content(type(self).__qualname__)
