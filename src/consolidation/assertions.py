"""Generate deterministic, reviewable assertion consolidation proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ConsolidationAction(StrEnum):
    DUPLICATE = "duplicate"
    SUPERSEDE = "supersede"


@dataclass(frozen=True, slots=True)
class AssertionCandidate:
    assertion_id: str
    subject_type: str
    subject_id: str | None
    predicate: str
    value: Any
    status: str
    authority: float
    confidence: float
    importance: float
    useful_count: int
    harmful_count: int
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    last_observed_at: datetime | None = None
    last_confirmed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationProposal:
    action: ConsolidationAction
    survivor_id: str
    redundant_id: str
    score: float
    reasons: tuple[str, ...]
    requires_human_review: bool = True


def canonical_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def same_assertion_key(left: AssertionCandidate, right: AssertionCandidate) -> bool:
    return (
        left.subject_type == right.subject_type
        and left.subject_id == right.subject_id
        and left.predicate == right.predicate
    )


def _timestamp(item: AssertionCandidate) -> datetime:
    value = item.last_confirmed_at or item.last_observed_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def survivor_rank(item: AssertionCandidate) -> tuple[float, float, int, int, float, datetime, str]:
    net_feedback = item.useful_count - item.harmful_count
    net_evidence = item.supporting_evidence_count - item.contradicting_evidence_count
    status_bonus = {"confirmed": 2, "active": 1, "candidate": 0}.get(item.status, -1)
    return (
        status_bonus,
        item.authority,
        net_evidence,
        net_feedback,
        item.confidence,
        _timestamp(item),
        item.assertion_id,
    )


def propose_consolidation(left: AssertionCandidate, right: AssertionCandidate) -> ConsolidationProposal | None:
    """Propose duplicate removal or supersession without mutating either assertion."""
    terminal = {"deleted", "archived", "superseded"}
    if left.assertion_id == right.assertion_id or left.status in terminal or right.status in terminal:
        return None
    if not same_assertion_key(left, right):
        return None

    survivor, redundant = sorted((left, right), key=survivor_rank, reverse=True)
    same_value = canonical_value(left.value) == canonical_value(right.value)
    if same_value:
        score = min(1.0, round(0.65 + 0.1 * max(survivor.authority, survivor.confidence), 3))
        return ConsolidationProposal(
            action=ConsolidationAction.DUPLICATE,
            survivor_id=survivor.assertion_id,
            redundant_id=redundant.assertion_id,
            score=score,
            reasons=(
                "same subject, predicate, and canonical value",
                "survivor selected by status, authority, evidence, feedback, confidence, and recency",
            ),
        )

    newer = _timestamp(survivor) > _timestamp(redundant)
    stronger = survivor_rank(survivor)[:-2] > survivor_rank(redundant)[:-2]
    evidence_margin = (
        survivor.supporting_evidence_count - survivor.contradicting_evidence_count
        - redundant.supporting_evidence_count + redundant.contradicting_evidence_count
    )
    if not newer or (not stronger and evidence_margin < 1):
        return None

    score = min(1.0, round(0.45 + 0.08 * max(0, evidence_margin) + 0.15 * survivor.authority, 3))
    return ConsolidationProposal(
        action=ConsolidationAction.SUPERSEDE,
        survivor_id=survivor.assertion_id,
        redundant_id=redundant.assertion_id,
        score=score,
        reasons=(
            "same subject and predicate but conflicting values",
            "selected survivor is newer and has stronger trust or evidence signals",
        ),
    )
