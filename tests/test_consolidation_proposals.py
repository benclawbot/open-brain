from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.consolidation.assertions import AssertionCandidate, propose_consolidation
from src.db.consolidation_queries import POLICY_VERSION, _fingerprint, _snapshot


def _row(value, *, authority=0.8, status="active"):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "id": uuid4(),
        "subject_type": "project",
        "subject_id": uuid4(),
        "predicate": "repository.default_branch",
        "value": value,
        "status": status,
        "authority": authority,
        "confidence": 0.8,
        "importance": 0.5,
        "useful_count": 3,
        "harmful_count": 0,
        "supporting_evidence_count": 2,
        "contradicting_evidence_count": 0,
        "last_observed_at": now,
        "last_confirmed_at": now,
    }


def _candidate(row):
    return AssertionCandidate(
        assertion_id=str(row["id"]),
        subject_type=row["subject_type"],
        subject_id=str(row["subject_id"]),
        predicate=row["predicate"],
        value=row["value"],
        status=row["status"],
        authority=row["authority"],
        confidence=row["confidence"],
        importance=row["importance"],
        useful_count=row["useful_count"],
        harmful_count=row["harmful_count"],
        supporting_evidence_count=row["supporting_evidence_count"],
        contradicting_evidence_count=row["contradicting_evidence_count"],
        last_observed_at=row["last_observed_at"],
        last_confirmed_at=row["last_confirmed_at"],
    )


def test_fingerprint_is_stable_for_same_pair_and_policy():
    subject_id = uuid4()
    left = _row({"branch": "main"})
    right = _row({"branch": "main"}, authority=0.6)
    left["subject_id"] = subject_id
    right["subject_id"] = subject_id
    proposal = propose_consolidation(_candidate(left), _candidate(right))
    survivor = left if proposal.survivor_id == str(left["id"]) else right
    redundant = right if survivor is left else left

    first = _fingerprint(proposal, survivor, redundant)
    second = _fingerprint(proposal, dict(survivor), dict(redundant))

    assert first == second
    assert len(first) == 64
    assert POLICY_VERSION == "assertion-consolidation-v1"


def test_snapshot_normalizes_identifiers_and_timestamps():
    row = _row(["a", "b"])
    snapshot = _snapshot(row)

    assert snapshot["id"] == str(row["id"])
    assert snapshot["subject_id"] == str(row["subject_id"])
    assert snapshot["last_observed_at"].endswith("+00:00")


def test_invalid_review_state_is_rejected_before_storage():
    from src.db.consolidation_queries import resolve_consolidation_proposal

    with pytest.raises(ValueError, match="accepted or rejected"):
        resolve_consolidation_proposal(uuid4(), state="pending", reviewed_by="tester")
