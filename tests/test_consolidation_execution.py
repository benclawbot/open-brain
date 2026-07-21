from copy import deepcopy
from uuid import uuid4

import pytest

from src.consolidation.execution import validate_execution_contract, validate_reversal_contract


def _assertion(*, status="active", assertion_id=None):
    return {
        "id": assertion_id or uuid4(),
        "subject_type": "project",
        "subject_id": uuid4(),
        "predicate": "repository.default_branch",
        "value": "main",
        "status": status,
        "authority": 0.8,
        "confidence": 0.8,
        "importance": 0.5,
        "useful_count": 4,
        "harmful_count": 0,
        "supporting_evidence_count": 2,
        "contradicting_evidence_count": 0,
        "last_observed_at": None,
        "last_confirmed_at": None,
        "superseded_by": None,
    }


def _proposal(survivor, redundant):
    from src.consolidation.execution import comparable_snapshot
    return {
        "state": "accepted",
        "action": "duplicate",
        "applied_at": None,
        "survivor_snapshot": comparable_snapshot(survivor),
        "redundant_snapshot": comparable_snapshot(redundant),
    }


def test_execution_accepts_unchanged_snapshots():
    survivor = _assertion()
    redundant = _assertion()
    validate_execution_contract(_proposal(survivor, redundant), survivor, redundant)


def test_execution_rejects_stale_redundant_snapshot():
    survivor = _assertion()
    redundant = _assertion()
    proposal = _proposal(survivor, redundant)
    changed = deepcopy(redundant)
    changed["value"] = "master"
    with pytest.raises(ValueError, match="redundant assertion changed"):
        validate_execution_contract(proposal, survivor, changed)


def test_execution_requires_accepted_proposal():
    survivor = _assertion()
    redundant = _assertion()
    proposal = _proposal(survivor, redundant)
    proposal["state"] = "pending"
    with pytest.raises(ValueError, match="must be accepted"):
        validate_execution_contract(proposal, survivor, redundant)


def test_reversal_rejects_changed_lineage():
    survivor = _assertion()
    redundant = _assertion(status="superseded")
    redundant["superseded_by"] = uuid4()
    execution = {
        "reversed_at": None,
        "survivor_id": survivor["id"],
    }
    with pytest.raises(ValueError, match="lineage changed"):
        validate_reversal_contract(execution, redundant)
