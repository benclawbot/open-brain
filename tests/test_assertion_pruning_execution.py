import pytest

from src.pruning.execution import (
    PruningConflict,
    validate_archive_contract,
    validate_restore_contract,
)


def snapshot(**overrides):
    values = {
        "status": "active", "temporal_class": "ephemeral", "authority": 0.3,
        "confidence": 0.3, "importance": 0.2, "access_count": 0,
        "useful_count": 0, "harmful_count": 0, "last_observed_at": "2026-01-01T00:00:00+00:00",
        "last_accessed_at": None, "valid_until": "2026-02-01T00:00:00+00:00",
        "superseded_by": None, "evidence_count": 2,
    }
    values.update(overrides)
    return values


def proposal(**overrides):
    values = {"state": "accepted", "applied_at": None, "assertion_snapshot": snapshot()}
    values.update(overrides)
    return values


def test_archive_requires_acceptance():
    with pytest.raises(PruningConflict, match="accepted"):
        validate_archive_contract(proposal(state="pending"), snapshot())


def test_archive_rejects_stale_snapshot():
    with pytest.raises(PruningConflict, match="confidence"):
        validate_archive_contract(proposal(), snapshot(confidence=0.8))


def test_archive_rejects_terminal_or_repeated_application():
    with pytest.raises(PruningConflict, match="terminal"):
        validate_archive_contract(proposal(), snapshot(status="archived"))
    with pytest.raises(PruningConflict, match="already applied"):
        validate_archive_contract(proposal(applied_at="now"), snapshot())


def test_archive_accepts_unchanged_snapshot():
    validate_archive_contract(proposal(), snapshot())


def test_restore_requires_untouched_archive_state_and_lineage():
    tombstone = {"reversed_at": None, "assertion_snapshot": snapshot()}
    validate_restore_contract(tombstone, snapshot(status="archived"))
    with pytest.raises(PruningConflict, match="status"):
        validate_restore_contract(tombstone, snapshot(status="active"))
    with pytest.raises(PruningConflict, match="lineage"):
        validate_restore_contract(tombstone, snapshot(status="archived", superseded_by="other"))


def test_restore_is_single_use():
    with pytest.raises(PruningConflict, match="already restored"):
        validate_restore_contract(
            {"reversed_at": "now", "assertion_snapshot": snapshot()},
            snapshot(status="archived"),
        )
