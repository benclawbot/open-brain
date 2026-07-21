"""Safety contracts for archival and restoration of assertions."""

from __future__ import annotations

from typing import Any


class PruningConflict(ValueError):
    """Raised when a pruning action is stale or unsafe."""


def validate_archive_contract(proposal: dict[str, Any], current: dict[str, Any]) -> None:
    if proposal["state"] != "accepted":
        raise PruningConflict("pruning proposal must be accepted")
    if current["status"] in {"archived", "deleted"}:
        raise PruningConflict("assertion is already terminal")
    if proposal.get("applied_at") is not None:
        raise PruningConflict("pruning proposal was already applied")
    snapshot = proposal["assertion_snapshot"]
    for key in (
        "status", "temporal_class", "authority", "confidence", "importance",
        "access_count", "useful_count", "harmful_count", "last_observed_at",
        "last_accessed_at", "valid_until", "superseded_by", "evidence_count",
    ):
        if current.get(key) != snapshot.get(key):
            raise PruningConflict(f"assertion changed after proposal generation: {key}")


def validate_restore_contract(tombstone: dict[str, Any], current: dict[str, Any]) -> None:
    if tombstone.get("reversed_at") is not None:
        raise PruningConflict("tombstone was already restored")
    if current.get("status") != "archived":
        raise PruningConflict("assertion status changed after archival")
    if current.get("superseded_by") != tombstone["assertion_snapshot"].get("superseded_by"):
        raise PruningConflict("assertion lineage changed after archival")
