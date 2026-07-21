"""Persistence helpers for reviewable assertion lifecycle proposals."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

try:
    from .connection import get_db_cursor
except ImportError:  # Support legacy execution with src/ directly on sys.path.
    from db.connection import get_db_cursor

try:
    from ..lifecycle.assertions import AssertionLifecycleInput, evaluate_assertion_lifecycle
except ImportError:  # Support legacy execution with src/ directly on sys.path.
    from lifecycle.assertions import AssertionLifecycleInput, evaluate_assertion_lifecycle

POLICY_VERSION = "assertion-lifecycle-v1"


def _fingerprint(assertion: dict[str, Any], proposal: Any) -> str:
    payload = {
        "assertion_id": str(assertion["id"]),
        "status": assertion["status"],
        "authority": float(assertion["authority"]),
        "confidence": float(assertion["confidence"]),
        "importance": float(assertion["importance"]),
        "access_count": int(assertion["access_count"]),
        "useful_count": int(assertion["useful_count"]),
        "harmful_count": int(assertion["harmful_count"]),
        "last_observed_at": assertion["last_observed_at"].isoformat() if assertion.get("last_observed_at") else None,
        "last_confirmed_at": assertion["last_confirmed_at"].isoformat() if assertion.get("last_confirmed_at") else None,
        "action": proposal.action.value,
        "target_status": proposal.target_status,
        "score": proposal.score,
        "reasons": list(proposal.reasons),
        "policy_version": POLICY_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def generate_lifecycle_proposals(*, limit: int = 250, minimum_score: float = 0.25) -> list[dict[str, Any]]:
    """Evaluate current assertions and persist idempotent review proposals."""
    created: list[dict[str, Any]] = []
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT a.*,
                   COUNT(e.id) FILTER (WHERE e.stance = 'supports') AS supporting_evidence_count,
                   COUNT(e.id) FILTER (WHERE e.stance = 'contradicts') AS contradicting_evidence_count
            FROM assertion a
            LEFT JOIN assertion_evidence e ON e.assertion_id = a.id
            WHERE a.status NOT IN ('deleted', 'archived', 'superseded')
            GROUP BY a.id
            ORDER BY a.importance DESC, a.last_confirmed_at DESC NULLS LAST, a.last_observed_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        assertions = [dict(row) for row in cursor.fetchall()]

        for assertion in assertions:
            proposal = evaluate_assertion_lifecycle(
                AssertionLifecycleInput(
                    assertion_id=str(assertion["id"]),
                    status=assertion["status"],
                    temporal_class=assertion["temporal_class"],
                    authority=float(assertion["authority"]),
                    confidence=float(assertion["confidence"]),
                    importance=float(assertion["importance"]),
                    access_count=int(assertion["access_count"]),
                    useful_count=int(assertion["useful_count"]),
                    harmful_count=int(assertion["harmful_count"]),
                    supporting_evidence_count=int(assertion["supporting_evidence_count"] or 0),
                    contradicting_evidence_count=int(assertion["contradicting_evidence_count"] or 0),
                    last_observed_at=assertion.get("last_observed_at"),
                    last_confirmed_at=assertion.get("last_confirmed_at"),
                )
            )
            if proposal.action.value == "keep" or proposal.score < minimum_score:
                continue

            fingerprint = _fingerprint(assertion, proposal)
            snapshot = {
                "status": assertion["status"],
                "predicate": assertion["predicate"],
                "value": assertion["value"],
                "authority": float(assertion["authority"]),
                "confidence": float(assertion["confidence"]),
                "importance": float(assertion["importance"]),
                "access_count": int(assertion["access_count"]),
                "useful_count": int(assertion["useful_count"]),
                "harmful_count": int(assertion["harmful_count"]),
            }
            cursor.execute(
                """
                INSERT INTO assertion_lifecycle_proposal (
                    assertion_id, action, target_status, score, reasons,
                    assertion_snapshot, policy_version, fingerprint
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                ON CONFLICT (assertion_id, fingerprint) DO NOTHING
                RETURNING *
                """,
                (
                    assertion["id"], proposal.action.value, proposal.target_status,
                    proposal.score, json.dumps(list(proposal.reasons)),
                    json.dumps(snapshot, default=str), POLICY_VERSION, fingerprint,
                ),
            )
            row = cursor.fetchone()
            if row:
                created.append(dict(row))
    return created


def list_lifecycle_proposals(*, state: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT p.*, a.predicate, a.value, a.status AS current_assertion_status
            FROM assertion_lifecycle_proposal p
            JOIN assertion a ON a.id = p.assertion_id
            WHERE p.state = %s
            ORDER BY p.score DESC, p.created_at ASC
            LIMIT %s
            """,
            (state, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def resolve_lifecycle_proposal(
    proposal_id: UUID,
    *,
    state: str,
    reviewed_by: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Record a review decision without mutating the target assertion."""
    if state not in {"accepted", "rejected"}:
        raise ValueError("state must be accepted or rejected")
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE assertion_lifecycle_proposal
            SET state = %s, reviewed_at = NOW(), reviewed_by = %s, review_note = %s
            WHERE id = %s AND state = 'pending'
            RETURNING *
            """,
            (state, reviewed_by, note, proposal_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
