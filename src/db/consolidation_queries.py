"""Persistence helpers for reviewable assertion consolidation proposals."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

try:
    from .connection import get_db_cursor
except ImportError:
    from db.connection import get_db_cursor

try:
    from ..consolidation.assertions import AssertionCandidate, propose_consolidation
except ImportError:
    from consolidation.assertions import AssertionCandidate, propose_consolidation

POLICY_VERSION = "assertion-consolidation-v1"


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "subject_type": row["subject_type"],
        "subject_id": str(row["subject_id"]) if row.get("subject_id") else None,
        "predicate": row["predicate"],
        "value": row["value"],
        "status": row["status"],
        "authority": float(row["authority"]),
        "confidence": float(row["confidence"]),
        "importance": float(row["importance"]),
        "useful_count": int(row["useful_count"]),
        "harmful_count": int(row["harmful_count"]),
        "supporting_evidence_count": int(row.get("supporting_evidence_count") or 0),
        "contradicting_evidence_count": int(row.get("contradicting_evidence_count") or 0),
        "last_observed_at": row["last_observed_at"].isoformat() if row.get("last_observed_at") else None,
        "last_confirmed_at": row["last_confirmed_at"].isoformat() if row.get("last_confirmed_at") else None,
    }


def _candidate(row: dict[str, Any]) -> AssertionCandidate:
    return AssertionCandidate(
        assertion_id=str(row["id"]), subject_type=row["subject_type"],
        subject_id=str(row["subject_id"]) if row.get("subject_id") else None,
        predicate=row["predicate"], value=row["value"], status=row["status"],
        authority=float(row["authority"]), confidence=float(row["confidence"]),
        importance=float(row["importance"]), useful_count=int(row["useful_count"]),
        harmful_count=int(row["harmful_count"]),
        supporting_evidence_count=int(row.get("supporting_evidence_count") or 0),
        contradicting_evidence_count=int(row.get("contradicting_evidence_count") or 0),
        last_observed_at=row.get("last_observed_at"), last_confirmed_at=row.get("last_confirmed_at"),
    )


def _fingerprint(proposal: Any, survivor: dict[str, Any], redundant: dict[str, Any]) -> str:
    payload = {
        "action": proposal.action.value,
        "survivor": _snapshot(survivor),
        "redundant": _snapshot(redundant),
        "score": proposal.score,
        "reasons": list(proposal.reasons),
        "policy_version": POLICY_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def generate_consolidation_proposals(*, limit: int = 500, minimum_score: float = 0.5) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT a.*,
                   COUNT(e.id) FILTER (WHERE e.stance = 'supports') AS supporting_evidence_count,
                   COUNT(e.id) FILTER (WHERE e.stance = 'contradicts') AS contradicting_evidence_count
            FROM assertion a LEFT JOIN assertion_evidence e ON e.assertion_id = a.id
            WHERE a.status NOT IN ('deleted', 'archived', 'superseded')
            GROUP BY a.id ORDER BY a.subject_type, a.subject_id, a.predicate, a.last_observed_at DESC
            LIMIT %s
        """, (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        groups: dict[tuple[str, str | None, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[(row["subject_type"], str(row["subject_id"]) if row.get("subject_id") else None, row["predicate"])].append(row)

        by_id = {str(row["id"]): row for row in rows}
        seen_pairs: set[tuple[str, str]] = set()
        for group in groups.values():
            for index, left in enumerate(group):
                for right in group[index + 1:]:
                    proposal = propose_consolidation(_candidate(left), _candidate(right))
                    if proposal is None or proposal.score < minimum_score:
                        continue
                    pair = tuple(sorted((proposal.survivor_id, proposal.redundant_id)))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    survivor = by_id[proposal.survivor_id]
                    redundant = by_id[proposal.redundant_id]
                    fingerprint = _fingerprint(proposal, survivor, redundant)
                    cursor.execute("""
                        INSERT INTO assertion_consolidation_proposal (
                            survivor_id, redundant_id, action, score, reasons,
                            survivor_snapshot, redundant_snapshot, policy_version, fingerprint
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                        ON CONFLICT (survivor_id, redundant_id, fingerprint) DO NOTHING RETURNING *
                    """, (proposal.survivor_id, proposal.redundant_id, proposal.action.value,
                            proposal.score, json.dumps(list(proposal.reasons)),
                            json.dumps(_snapshot(survivor), default=str),
                            json.dumps(_snapshot(redundant), default=str), POLICY_VERSION, fingerprint))
                    row = cursor.fetchone()
                    if row:
                        created.append(dict(row))
    return created


def list_consolidation_proposals(*, state: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT p.*, s.predicate, s.value AS survivor_value, r.value AS redundant_value
            FROM assertion_consolidation_proposal p
            JOIN assertion s ON s.id = p.survivor_id
            JOIN assertion r ON r.id = p.redundant_id
            WHERE p.state = %s ORDER BY p.score DESC, p.created_at ASC LIMIT %s
        """, (state, limit))
        return [dict(row) for row in cursor.fetchall()]


def resolve_consolidation_proposal(proposal_id: UUID, *, state: str, reviewed_by: str, note: str | None = None) -> dict[str, Any] | None:
    if state not in {"accepted", "rejected"}:
        raise ValueError("state must be accepted or rejected")
    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE assertion_consolidation_proposal
            SET state = %s, reviewed_at = NOW(), reviewed_by = %s, review_note = %s
            WHERE id = %s AND state = 'pending' RETURNING *
        """, (state, reviewed_by, note, proposal_id))
        row = cursor.fetchone()
        return dict(row) if row else None
