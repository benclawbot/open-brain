from datetime import datetime, timedelta, timezone

from src.lifecycle.assertions import (
    AssertionLifecycleInput,
    LifecycleAction,
    evaluate_assertion_lifecycle,
)


NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _assertion(**overrides):
    values = {
        "assertion_id": "assertion-1",
        "status": "active",
        "temporal_class": "slow-changing",
        "authority": 0.8,
        "confidence": 0.8,
        "importance": 0.7,
        "access_count": 3,
        "useful_count": 2,
        "harmful_count": 0,
        "supporting_evidence_count": 1,
        "contradicting_evidence_count": 0,
        "last_observed_at": NOW - timedelta(days=10),
    }
    values.update(overrides)
    return AssertionLifecycleInput(**values)


def test_healthy_assertion_is_kept():
    proposal = evaluate_assertion_lifecycle(_assertion(), now=NOW)

    assert proposal.action is LifecycleAction.KEEP
    assert proposal.target_status is None
    assert proposal.requires_human_review is True


def test_single_harmful_feedback_cannot_demote_assertion():
    proposal = evaluate_assertion_lifecycle(
        _assertion(useful_count=0, harmful_count=1, access_count=1),
        now=NOW,
    )

    assert proposal.action is LifecycleAction.KEEP
    assert proposal.score < 0.25


def test_repeated_harm_and_contradiction_propose_demotion():
    proposal = evaluate_assertion_lifecycle(
        _assertion(
            useful_count=1,
            harmful_count=3,
            contradicting_evidence_count=1,
        ),
        now=NOW,
    )

    assert proposal.action is LifecycleAction.DEMOTE
    assert proposal.target_status == "dormant"
    assert any("harmful feedback ratio" in reason for reason in proposal.reasons)
    assert any("contradicting evidence" in reason for reason in proposal.reasons)


def test_stale_low_value_high_risk_assertion_proposes_archival():
    proposal = evaluate_assertion_lifecycle(
        _assertion(
            temporal_class="project-state",
            importance=0.2,
            useful_count=0,
            harmful_count=3,
            contradicting_evidence_count=2,
            last_observed_at=NOW - timedelta(days=120),
        ),
        now=NOW,
    )

    assert proposal.action is LifecycleAction.ARCHIVE
    assert proposal.target_status == "archived"


def test_confirmed_assertion_is_never_proposed_for_archive_or_demotion():
    proposal = evaluate_assertion_lifecycle(
        _assertion(
            status="confirmed",
            temporal_class="ephemeral",
            importance=0.1,
            useful_count=0,
            harmful_count=10,
            contradicting_evidence_count=5,
            last_observed_at=NOW - timedelta(days=30),
        ),
        now=NOW,
    )

    assert proposal.action is LifecycleAction.REVIEW
    assert proposal.target_status is None


def test_terminal_assertion_is_not_reprocessed():
    proposal = evaluate_assertion_lifecycle(
        _assertion(status="archived", harmful_count=9),
        now=NOW,
    )

    assert proposal.action is LifecycleAction.KEEP
    assert proposal.reasons == ("assertion is already in a terminal lifecycle state",)
