"""Generate reviewable assertion lifecycle proposals without mutating knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class LifecycleAction(StrEnum):
    KEEP = "keep"
    REVIEW = "review"
    DEMOTE = "demote"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class AssertionLifecycleInput:
    assertion_id: str
    status: str
    temporal_class: str
    authority: float
    confidence: float
    importance: float
    access_count: int
    useful_count: int
    harmful_count: int
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    last_observed_at: datetime | None = None
    last_confirmed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AssertionLifecycleProposal:
    assertion_id: str
    action: LifecycleAction
    target_status: str | None
    score: float
    reasons: tuple[str, ...]
    requires_human_review: bool = True


def _age_days(value: datetime | None, now: datetime) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, (now - value).days)


def _stale_after_days(temporal_class: str) -> int:
    return {
        "stable": 365,
        "slow-changing": 120,
        "project-state": 30,
        "session-state": 7,
        "ephemeral": 1,
    }.get(temporal_class, 90)


def evaluate_assertion_lifecycle(
    item: AssertionLifecycleInput,
    *,
    now: datetime | None = None,
) -> AssertionLifecycleProposal:
    """Return a conservative, explainable lifecycle proposal.

    This function never mutates an assertion. Confirmed assertions are never
    automatically proposed for archival, and low sample counts cannot trigger
    demotion solely from a single harmful feedback event.
    """
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    review_score = 0.0

    observed_age = _age_days(item.last_confirmed_at or item.last_observed_at, now)
    stale_after = _stale_after_days(item.temporal_class)
    is_stale = observed_age is not None and observed_age >= stale_after
    if is_stale:
        review_score += min(0.35, observed_age / max(stale_after, 1) * 0.15)
        reasons.append(f"not confirmed or observed for {observed_age} days")

    feedback_total = item.useful_count + item.harmful_count
    harmful_ratio = item.harmful_count / feedback_total if feedback_total else 0.0
    if item.harmful_count >= 2 and harmful_ratio >= 0.5:
        review_score += 0.45
        reasons.append(
            f"harmful feedback ratio is {harmful_ratio:.0%} across {feedback_total} rated uses"
        )
    elif item.harmful_count == 1:
        review_score += 0.1
        reasons.append("one harmful use has been reported; more evidence is required")

    if item.contradicting_evidence_count:
        review_score += min(0.4, item.contradicting_evidence_count * 0.2)
        reasons.append(f"{item.contradicting_evidence_count} contradicting evidence record(s)")

    if item.supporting_evidence_count == 0 and item.authority < 0.5 and item.confidence < 0.5:
        review_score += 0.2
        reasons.append("low-authority, low-confidence assertion has no supporting evidence")

    if item.access_count >= 5 and item.useful_count == 0:
        review_score += 0.1
        reasons.append("frequently accessed without any recorded useful outcome")

    review_score = min(1.0, round(review_score, 3))

    if item.status in {"deleted", "archived", "superseded"}:
        return AssertionLifecycleProposal(
            assertion_id=item.assertion_id,
            action=LifecycleAction.KEEP,
            target_status=None,
            score=review_score,
            reasons=("assertion is already in a terminal lifecycle state",),
        )

    if item.status == "confirmed":
        action = LifecycleAction.REVIEW if review_score >= 0.45 else LifecycleAction.KEEP
        return AssertionLifecycleProposal(
            assertion_id=item.assertion_id,
            action=action,
            target_status=None,
            score=review_score,
            reasons=tuple(reasons) or ("confirmed assertion remains healthy",),
        )

    if review_score >= 0.8 and is_stale and item.importance < 0.4:
        return AssertionLifecycleProposal(
            assertion_id=item.assertion_id,
            action=LifecycleAction.ARCHIVE,
            target_status="archived",
            score=review_score,
            reasons=tuple(reasons),
        )

    if review_score >= 0.55:
        return AssertionLifecycleProposal(
            assertion_id=item.assertion_id,
            action=LifecycleAction.DEMOTE,
            target_status="dormant",
            score=review_score,
            reasons=tuple(reasons),
        )

    if review_score >= 0.25:
        return AssertionLifecycleProposal(
            assertion_id=item.assertion_id,
            action=LifecycleAction.REVIEW,
            target_status=None,
            score=review_score,
            reasons=tuple(reasons),
        )

    return AssertionLifecycleProposal(
        assertion_id=item.assertion_id,
        action=LifecycleAction.KEEP,
        target_status=None,
        score=review_score,
        reasons=tuple(reasons) or ("no lifecycle risk threshold reached",),
    )
