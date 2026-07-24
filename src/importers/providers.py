"""Provider-specific normalization for external long-term memory systems.

Adapters are deliberately read-only. They convert exported/provider API records into
Open Brain ``ImportCandidate`` objects while preserving provenance and provider
semantics for later reconciliation.
"""

from __future__ import annotations

import json
from abc import abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .base import ImportAdapter, ImportCandidate, ImportSource, hash_content


class ProviderCapability(StrEnum):
    MEMORIES = "memories"
    USER_PROFILE = "user_profile"
    SESSIONS = "sessions"
    ENTITIES = "entities"
    RELATIONSHIPS = "relationships"
    TEMPORAL_VALIDITY = "temporal_validity"
    CONFIDENCE = "confidence"
    CUSTOM_METADATA = "custom_metadata"


class ProviderDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    version: str | None = Field(default=None, max_length=100)
    capabilities: frozenset[ProviderCapability]
    inferred_authority: str = Field(default="provider_inferred", max_length=100)


class ProviderExportAdapter(ImportAdapter):
    """Base adapter for records already exported from a memory provider."""

    descriptor: ProviderDescriptor

    def __init__(self, records: Sequence[Mapping[str, Any]], *, source_instance: str | None = None):
        self.records = list(records)
        self.source_instance = source_instance

    def source_fingerprint(self) -> str:
        payload = {
            "provider": self.descriptor.name,
            "version": self.descriptor.version,
            "source_instance": self.source_instance,
            "records": self.records,
        }
        return hash_content(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")))

    def discover(self) -> Iterable[ImportCandidate]:
        for ordinal, record in enumerate(self.records, start=1):
            candidate = self.normalize(record, ordinal=ordinal)
            if candidate is not None:
                yield candidate

    @abstractmethod
    def normalize(self, record: Mapping[str, Any], *, ordinal: int) -> ImportCandidate | None:
        """Normalize one provider record without modifying the source record."""

    def _candidate(
        self,
        *,
        external_id: str,
        content: str,
        record_type: str,
        raw: Mapping[str, Any],
        authority: str | None = None,
        observed_at: Any = None,
        provider_metadata: Mapping[str, Any] | None = None,
    ) -> ImportCandidate | None:
        normalized_content = content.strip()
        if not normalized_content:
            return None
        metadata = {
            "provider": self.descriptor.name,
            "provider_version": self.descriptor.version,
            "source_instance": self.source_instance,
            "provider_capabilities": sorted(item.value for item in self.descriptor.capabilities),
            "provider_metadata": dict(provider_metadata or {}),
            "observed_at": _normalize_timestamp(observed_at),
            "raw_record_hash": hash_content(json.dumps(raw, sort_keys=True, default=str, separators=(",", ":"))),
        }
        return ImportCandidate(
            external_id=f"{self.descriptor.name}:{external_id}",
            external_hash=hash_content(normalized_content),
            source=ImportSource.MEMORY_PROVIDER,
            content=normalized_content,
            record_type=record_type,
            authority=authority or self.descriptor.inferred_authority,
            metadata=metadata,
        )


class Mem0ExportAdapter(ProviderExportAdapter):
    descriptor = ProviderDescriptor(
        name="mem0",
        capabilities=frozenset(
            {
                ProviderCapability.MEMORIES,
                ProviderCapability.USER_PROFILE,
                ProviderCapability.TEMPORAL_VALIDITY,
                ProviderCapability.CUSTOM_METADATA,
            }
        ),
    )

    def normalize(self, record: Mapping[str, Any], *, ordinal: int) -> ImportCandidate | None:
        external_id = str(record.get("id") or record.get("memory_id") or ordinal)
        content = str(record.get("memory") or record.get("content") or record.get("text") or "")
        metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
        return self._candidate(
            external_id=external_id,
            content=content,
            record_type="memory",
            raw=record,
            observed_at=record.get("updated_at") or record.get("created_at"),
            provider_metadata=metadata,
        )


class HonchoExportAdapter(ProviderExportAdapter):
    descriptor = ProviderDescriptor(
        name="honcho",
        capabilities=frozenset(
            {
                ProviderCapability.MEMORIES,
                ProviderCapability.USER_PROFILE,
                ProviderCapability.SESSIONS,
                ProviderCapability.ENTITIES,
                ProviderCapability.RELATIONSHIPS,
                ProviderCapability.CONFIDENCE,
                ProviderCapability.CUSTOM_METADATA,
            }
        ),
    )

    def normalize(self, record: Mapping[str, Any], *, ordinal: int) -> ImportCandidate | None:
        external_id = str(record.get("id") or record.get("representation_id") or ordinal)
        content = str(
            record.get("content")
            or record.get("representation")
            or record.get("observation")
            or record.get("text")
            or ""
        )
        record_type = "user_profile" if record.get("type") in {"representation", "profile"} else "memory"
        provider_metadata = {
            key: record[key]
            for key in ("peer_id", "session_id", "confidence", "type")
            if record.get(key) is not None
        }
        return self._candidate(
            external_id=external_id,
            content=content,
            record_type=record_type,
            raw=record,
            observed_at=record.get("updated_at") or record.get("created_at"),
            provider_metadata=provider_metadata,
        )


class HindsightExportAdapter(ProviderExportAdapter):
    descriptor = ProviderDescriptor(
        name="hindsight",
        capabilities=frozenset(
            {
                ProviderCapability.MEMORIES,
                ProviderCapability.SESSIONS,
                ProviderCapability.ENTITIES,
                ProviderCapability.RELATIONSHIPS,
                ProviderCapability.TEMPORAL_VALIDITY,
                ProviderCapability.CONFIDENCE,
                ProviderCapability.CUSTOM_METADATA,
            }
        ),
    )

    def normalize(self, record: Mapping[str, Any], *, ordinal: int) -> ImportCandidate | None:
        external_id = str(record.get("id") or record.get("memory_id") or ordinal)
        content = str(record.get("text") or record.get("content") or record.get("memory") or "")
        provider_metadata = {
            key: record[key]
            for key in ("bank_id", "document_id", "session_id", "confidence", "entities", "relations")
            if record.get(key) is not None
        }
        return self._candidate(
            external_id=external_id,
            content=content,
            record_type=str(record.get("type") or "memory"),
            raw=record,
            observed_at=record.get("timestamp") or record.get("updated_at") or record.get("created_at"),
            provider_metadata=provider_metadata,
        )


_PROVIDER_ADAPTERS = {
    "mem0": Mem0ExportAdapter,
    "honcho": HonchoExportAdapter,
    "hindsight": HindsightExportAdapter,
}


def provider_adapter(
    provider: str,
    records: Sequence[Mapping[str, Any]],
    *,
    source_instance: str | None = None,
) -> ProviderExportAdapter:
    """Construct a supported provider adapter by stable provider name."""
    normalized = provider.strip().lower()
    try:
        adapter_type = _PROVIDER_ADAPTERS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(_PROVIDER_ADAPTERS))
        raise ValueError(f"unsupported memory provider: {provider}; supported: {supported}") from exc
    return adapter_type(records, source_instance=source_instance)


def provider_descriptors() -> list[ProviderDescriptor]:
    return [adapter.descriptor for _, adapter in sorted(_PROVIDER_ADAPTERS.items())]


def _normalize_timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
