from uuid import uuid4

import pytest

from src.lifecycle.execution import (
    LifecycleExecutionError,
    compare_assertion_snapshot,
    validate_execution_contract,
    validate_reversal_contract,
)


def _assertion(status: str = "active") -> dict:
    return {
        "id": uuid4(),
        "status": status,
        "predicate": "repository.default_branch",
        "value": "master",
        "authority": 0.4,
        "confidence": 0.4,
        "importance": 0.3,
        "access_count": 8,
        "useful_count": 1,
        "harmful_count": 3,
    }


def _proposal(assertion: dict, target: str = "dormant") -> dict:
    return {
        "state": "accepted",
        "target_status": target,
        "applied_at": None,
        "assertion_snapshot": {k: assertion[k] for k in (
            "status", "predicate", "value", "authority", "confidence",
            "importance", "access_count", "useful_count", "harmful_count",
        )},
    }


def test_snapshot_comparison_reports_changed_fields():
    current = _assertion()
    snapshot = dict(current)
    snapshot["harmful_count"] = 2
    snapshot["value"] = "main"

    result = compare_assertion_snapshot(current, snapshot)

    assert result.matches is False
    assert set(result.changed_fields) == {"value", "harmful_count"}


def test_execution_rejects_stale_snapshot():
    current = _assertion()
    proposal = _proposal(current)
    current["value"] = "main"

    with pytest.raises(LifecycleExecutionError, match="changed since proposal generation"):
        validate_execution_contract(proposal, current)


def test_execution_rejects_confirmed_assertion():
    current = _assertion("confirmed")
    proposal = _proposal(current)

    with pytest.raises(LifecycleExecutionError, match="confirmed assertions"):
        validate_execution_contract(proposal, current)


def test_execution_rejects_unaccepted_and_duplicate_application():
    current = _assertion()
    proposal = _proposal(current)
    proposal["state"] = "pending"
    with pytest.raises(LifecycleExecutionError, match="accepted"):
        validate_execution_contract(proposal, current)

    proposal["state"] = "accepted"
    proposal["applied_at"] = "2026-07-21T16:00:00Z"
    with pytest.raises(LifecycleExecutionError, match="already been applied"):
        validate_execution_contract(proposal, current)


def test_reversal_requires_unchanged_applied_status_and_is_one_step():
    execution = {
        "previous_status": "active",
        "applied_status": "dormant",
        "reversed_at": None,
    }
    assert validate_reversal_contract(execution, {"status": "dormant"}) == "active"

    with pytest.raises(LifecycleExecutionError, match="changed after"):
        validate_reversal_contract(execution, {"status": "archived"})

    execution["reversed_at"] = "2026-07-21T16:00:00Z"
    with pytest.raises(LifecycleExecutionError, match="already been reversed"):
        validate_reversal_contract(execution, {"status": "dormant"})
