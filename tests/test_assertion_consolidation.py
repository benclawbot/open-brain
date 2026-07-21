from datetime import datetime, timezone

from src.consolidation.assertions import (
    AssertionCandidate,
    ConsolidationAction,
    canonical_value,
    propose_consolidation,
)


def candidate(assertion_id: str, value, **overrides) -> AssertionCandidate:
    data = {
        "assertion_id": assertion_id,
        "subject_type": "project",
        "subject_id": "project-1",
        "predicate": "repository.default_branch",
        "value": value,
        "status": "active",
        "authority": 0.6,
        "confidence": 0.7,
        "importance": 0.5,
        "useful_count": 1,
        "harmful_count": 0,
        "supporting_evidence_count": 1,
        "contradicting_evidence_count": 0,
        "last_observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    data.update(overrides)
    return AssertionCandidate(**data)


def test_canonical_value_ignores_mapping_order():
    assert canonical_value({"a": 1, "b": 2}) == canonical_value({"b": 2, "a": 1})


def test_exact_duplicate_selects_stronger_survivor():
    weaker = candidate("a", {"branch": "main"}, authority=0.4, confidence=0.4)
    stronger = candidate("b", {"branch": "main"}, status="confirmed", authority=0.9)

    proposal = propose_consolidation(weaker, stronger)

    assert proposal is not None
    assert proposal.action is ConsolidationAction.DUPLICATE
    assert proposal.survivor_id == "b"
    assert proposal.redundant_id == "a"
    assert proposal.requires_human_review is True


def test_conflicting_newer_stronger_assertion_can_supersede():
    old = candidate("old", "master", authority=0.4)
    new = candidate(
        "new",
        "main",
        status="confirmed",
        authority=0.9,
        supporting_evidence_count=3,
        last_confirmed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    proposal = propose_consolidation(old, new)

    assert proposal is not None
    assert proposal.action is ConsolidationAction.SUPERSEDE
    assert proposal.survivor_id == "new"
    assert proposal.redundant_id == "old"


def test_ambiguous_conflict_produces_no_proposal():
    left = candidate("left", "master")
    right = candidate("right", "main")

    assert propose_consolidation(left, right) is None


def test_different_subject_or_predicate_never_consolidates():
    left = candidate("left", "main")
    right = candidate("right", "main", subject_id="project-2")

    assert propose_consolidation(left, right) is None


def test_terminal_assertions_are_not_reopened():
    left = candidate("left", "main", status="archived")
    right = candidate("right", "main")

    assert propose_consolidation(left, right) is None
