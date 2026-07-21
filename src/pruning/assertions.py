"""Conservative assertion pruning policy.

The policy never hard-deletes knowledge. It only proposes archival candidates and
captures enough context for later tombstone creation and reversal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class PruningReason(StrEnum):
    EXPIRED_EPHEMERAL = "expired_ephemeral"
    STALE_SESSION_STATE = "stale_session_state"
    HARMFUL_LOW_VALUE = "harmful_low_value"
    SUPERSEDED_OLD = "superseded_old"
    CONTRADICTED_OLD = "contradicted_old"


@dataclass(frozen=True, slots=True)
class PruningCandidate:
    assertion_id: str
    status: str
    temporal_class: str
    authority: float
    confidence: float
    importance: float
    access_count: int
    useful_count: int
    harmful_count: int
    evidence_count: int
    last_observed_at: datetime
    last_accessed_at: datetime | None = None
    valid_until: datetime | None = None
    superseded_by: str | None = None


@dataclass(frozen=True, slots=True)
class PruningProposal:
    assertion_id: str
    reason: PruningReason
    score: float
    retention_days: int
    requires_human_review: bool = True


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_days(value: datetime, now: datetime) -> int:
    return max(0, (_utc(now) - _utc(value)).days)


def propose_pruning(candidate: PruningCandidate, *, now: datetime | None = None) -> PruningProposal | None:
    """Return an archival proposal only when conservative safety gates pass."""
    now = now or datetime.now(timezone.utc)
    if candidate.status in {"archived", "deleted"}:
        return None

    # Strong or repeatedly useful knowledge remains directly retrievable.
    if candidate.importance >= 0.75 or candidate.authority >= 0.85:
        return None
    if candidate.useful_count >= 3 or candidate.access_count >= 20:
        return None

    age = _age_days(candidate.last_observed_at, now)
    idle = _age_days(candidate.last_accessed_at or candidate.last_observed_at, now)

    if candidate.temporal_class == "ephemeral":
        expired = candidate.valid_until is not None and _utc(candidate.valid_until) < _utc(now)
        if expired or age >= 30:
            return PruningProposal(candidate.assertion_id, PruningReason.EXPIRED_EPHEMERAL, 0.95, 30)

    if candidate.temporal_class == "session-state" and age >= 60 and idle >= 45:
        return PruningProposal(candidate.assertion_id, PruningReason.STALE_SESSION_STATE, 0.85, 90)

    net_feedback = candidate.useful_count - candidate.harmful_count
    if candidate.harmful_count >= 2 and net_feedback <= -2 and candidate.confidence <= 0.45 and age >= 30:
        return PruningProposal(candidate.assertion_id, PruningReason.HARMFUL_LOW_VALUE, 0.9, 180)

    if candidate.status == "superseded" and candidate.superseded_by and age >= 90:
        return PruningProposal(candidate.assertion_id, PruningReason.SUPERSEDED_OLD, 0.8, 365)

    if candidate.status == "contradicted" and age >= 180 and candidate.evidence_count > 0:
        return PruningProposal(candidate.assertion_id, PruningReason.CONTRADICTED_OLD, 0.7, 365)

    return None
