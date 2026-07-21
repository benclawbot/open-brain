from datetime import datetime, timedelta, timezone

from src.pruning.assertions import PruningCandidate, PruningReason, propose_pruning

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def candidate(**overrides):
    values = dict(
        assertion_id="a-1", status="active", temporal_class="slow-changing",
        authority=0.4, confidence=0.4, importance=0.3, access_count=0,
        useful_count=0, harmful_count=0, evidence_count=0,
        last_observed_at=NOW - timedelta(days=200), last_accessed_at=None,
        valid_until=None, superseded_by=None,
    )
    values.update(overrides)
    return PruningCandidate(**values)


def test_expired_ephemeral_is_proposed():
    proposal = propose_pruning(candidate(
        temporal_class="ephemeral", valid_until=NOW - timedelta(days=1),
        last_observed_at=NOW - timedelta(days=10),
    ), now=NOW)
    assert proposal is not None
    assert proposal.reason == PruningReason.EXPIRED_EPHEMERAL


def test_high_value_assertion_is_never_proposed():
    assert propose_pruning(candidate(importance=0.9, temporal_class="ephemeral"), now=NOW) is None
    assert propose_pruning(candidate(authority=0.9, status="superseded", superseded_by="a-2"), now=NOW) is None


def test_useful_or_frequently_accessed_assertion_is_protected():
    assert propose_pruning(candidate(useful_count=3, status="contradicted", evidence_count=2), now=NOW) is None
    assert propose_pruning(candidate(access_count=20, status="superseded", superseded_by="a-2"), now=NOW) is None


def test_harmful_low_confidence_assertion_is_proposed():
    proposal = propose_pruning(candidate(
        harmful_count=3, useful_count=0, confidence=0.3,
        last_observed_at=NOW - timedelta(days=40),
    ), now=NOW)
    assert proposal is not None
    assert proposal.reason == PruningReason.HARMFUL_LOW_VALUE


def test_superseded_requires_lineage_and_age():
    assert propose_pruning(candidate(status="superseded", superseded_by=None), now=NOW) is None
    proposal = propose_pruning(candidate(
        status="superseded", superseded_by="a-2",
        last_observed_at=NOW - timedelta(days=100),
    ), now=NOW)
    assert proposal is not None
    assert proposal.reason == PruningReason.SUPERSEDED_OLD


def test_contradicted_requires_evidence():
    assert propose_pruning(candidate(status="contradicted", evidence_count=0), now=NOW) is None
    proposal = propose_pruning(candidate(status="contradicted", evidence_count=1), now=NOW)
    assert proposal is not None
    assert proposal.reason == PruningReason.CONTRADICTED_OLD


def test_archived_and_deleted_are_terminal():
    assert propose_pruning(candidate(status="archived"), now=NOW) is None
    assert propose_pruning(candidate(status="deleted"), now=NOW) is None
