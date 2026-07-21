from __future__ import annotations

import pytest

from src.importers.providers import (
    HindsightExportAdapter,
    HonchoExportAdapter,
    Mem0ExportAdapter,
    ProviderCapability,
    provider_adapter,
    provider_descriptors,
)


def test_mem0_normalization_preserves_provenance():
    candidate = next(
        iter(
            Mem0ExportAdapter(
                [
                    {
                        "id": "m-1",
                        "memory": "User prefers upstream Hermes.",
                        "created_at": "2026-07-21T10:00:00Z",
                        "metadata": {"user_id": "ben"},
                    }
                ],
                source_instance="workspace-a",
            ).discover()
        )
    )

    assert candidate.external_id == "mem0:m-1"
    assert candidate.authority == "provider_inferred"
    assert candidate.metadata["provider"] == "mem0"
    assert candidate.metadata["source_instance"] == "workspace-a"
    assert candidate.metadata["provider_metadata"]["user_id"] == "ben"


def test_honcho_representation_becomes_user_profile_candidate():
    candidate = next(
        iter(
            HonchoExportAdapter(
                [
                    {
                        "representation_id": "r-7",
                        "representation": "Ben values continuity across agents.",
                        "type": "representation",
                        "peer_id": "peer-1",
                        "confidence": 0.93,
                    }
                ]
            ).discover()
        )
    )

    assert candidate.record_type == "user_profile"
    assert candidate.metadata["provider_metadata"]["confidence"] == 0.93
    assert ProviderCapability.RELATIONSHIPS in HonchoExportAdapter.descriptor.capabilities


def test_hindsight_preserves_entities_relationships_and_timestamp():
    candidate = next(
        iter(
            HindsightExportAdapter(
                [
                    {
                        "memory_id": "h-9",
                        "text": "Open Brain is linked to Hermes.",
                        "timestamp": "2026-07-21T12:00:00Z",
                        "entities": ["Open Brain", "Hermes"],
                        "relations": [{"type": "integrates_with"}],
                    }
                ]
            ).discover()
        )
    )

    assert candidate.metadata["observed_at"] == "2026-07-21T12:00:00Z"
    assert candidate.metadata["provider_metadata"]["entities"] == ["Open Brain", "Hermes"]
    assert candidate.metadata["provider_metadata"]["relations"][0]["type"] == "integrates_with"


def test_blank_provider_records_are_skipped():
    assert list(Mem0ExportAdapter([{"id": "empty", "memory": "  "}]).discover()) == []


def test_source_fingerprint_changes_with_records():
    first = Mem0ExportAdapter([{"id": "1", "memory": "a"}]).source_fingerprint()
    second = Mem0ExportAdapter([{"id": "1", "memory": "b"}]).source_fingerprint()
    assert first != second


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unsupported memory provider"):
        provider_adapter("unknown", [{"id": "1", "content": "x"}])


def test_descriptors_are_stable_and_capability_rich():
    descriptors = provider_descriptors()
    assert [descriptor.name for descriptor in descriptors] == ["hindsight", "honcho", "mem0"]
    assert all(ProviderCapability.MEMORIES in descriptor.capabilities for descriptor in descriptors)
