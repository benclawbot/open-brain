from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.db.lifecycle_queries import POLICY_VERSION, _fingerprint
from src.lifecycle.assertions import AssertionLifecycleInput, evaluate_assertion_lifecycle


def _assertion() -> dict:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "id": uuid4(),
        "status": "active",
        "predicate": "repository.default_branch",
        "value": "master",
        "authority": 0.4,
        "confidence": 0.4,
        "importance": 0.3,
        "access_count": 8,
        "useful_count": 1,
        "harmful_count": 3,
        "last_observed_at": now,
        "last_confirmed_at": None,
    }


def _proposal(assertion: dict):
    return evaluate_assertion_lifecycle(
        AssertionLifecycleInput(
            assertion_id=str(assertion["id"]),
            status=assertion["status"],
            temporal_class="project-state",
            authority=assertion["authority"],
            confidence=assertion["confidence"],
            importance=assertion["importance"],
            access_count=assertion["access_count"],
            useful_count=assertion["useful_count"],
            harmful_count=assertion["harmful_count"],
            contradicting_evidence_count=2,
            last_observed_at=assertion["last_observed_at"],
        ),
        now=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )


def test_fingerprint_is_stable_for_same_assertion_snapshot_and_policy():
    assertion = _assertion()
    proposal = _proposal(assertion)

    first = _fingerprint(assertion, proposal)
    second = _fingerprint(dict(assertion), proposal)

    assert first == second
    assert len(first) == 64
    assert POLICY_VERSION in "assertion-lifecycle-v1"


def test_fingerprint_changes_when_feedback_changes():
    assertion = _assertion()
    proposal = _proposal(assertion)
    first = _fingerprint(assertion, proposal)

    assertion["harmful_count"] += 1
    changed = _fingerprint(assertion, _proposal(assertion))

    assert changed != first


def test_review_endpoint_contract_rejects_invalid_state_before_storage():
    from src.db.lifecycle_queries import resolve_lifecycle_proposal

    with pytest.raises(ValueError, match="accepted or rejected"):
        resolve_lifecycle_proposal(
            uuid4(),
            state="pending",
            reviewed_by="tester",
        )
