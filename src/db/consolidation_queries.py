"""Persistence helpers for reviewable assertion consolidation proposals."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from .connection import get_db_cursor

from ..consolidation.assertions import AssertionCandidate, propose_consolidation
from ..consolidation.execution import validate_execution_contract, validate_reversal_contract

POLICY_VERSION = "assertion-consolidation-v1"


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]), "subject_type": row["subject_type"],
        "subject_id": str(row["subject_id"]) if row.get("subject_id") else None,
        "predicate": row["predicate"], "value": row["value"], "status": row["status"],
        "authority": float(row["authority"]), "confidence": float(row["confidence"]),
        "importance": float(row["importance"]), "useful_count": int(row["useful_count"]),
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
    payload = {"action": proposal.action.value, "survivor": _snapshot(survivor),
               "redundant": _snapshot(redundant), "score": proposal.score,
               "reasons": list(proposal.reasons), "policy_version": POLICY_VERSION}
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
                    survivor, redundant = by_id[proposal.survivor_id], by_id[proposal.redundant_id]
                    cursor.execute("""
                        INSERT INTO assertion_consolidation_proposal (
                            survivor_id, redundant_id, action, score, reasons,
                            survivor_snapshot, redundant_snapshot, policy_version, fingerprint
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                        ON CONFLICT (survivor_id, redundant_id, fingerprint) DO NOTHING RETURNING *
                    """, (proposal.survivor_id, proposal.redundant_id, proposal.action.value,
                            proposal.score, json.dumps(list(proposal.reasons)),
                            json.dumps(_snapshot(survivor), default=str),
                            json.dumps(_snapshot(redundant), default=str), POLICY_VERSION,
                            _fingerprint(proposal, survivor, redundant)))
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


def _locked_assertion(cursor: Any, assertion_id: UUID) -> dict[str, Any]:
    cursor.execute("""
        SELECT a.*,
          (SELECT COUNT(*) FROM assertion_evidence e WHERE e.assertion_id=a.id AND e.stance='supports') AS supporting_evidence_count,
          (SELECT COUNT(*) FROM assertion_evidence e WHERE e.assertion_id=a.id AND e.stance='contradicts') AS contradicting_evidence_count
        FROM assertion a WHERE a.id=%s FOR UPDATE
    """, (assertion_id,))
    return dict(cursor.fetchone())


def apply_consolidation_proposal(proposal_id: UUID, *, applied_by: str) -> dict[str, Any] | None:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM assertion_consolidation_proposal WHERE id=%s FOR UPDATE", (proposal_id,))
        row = cursor.fetchone()
        if not row:
            return None
        proposal = dict(row)
        survivor = _locked_assertion(cursor, proposal["survivor_id"])
        redundant = _locked_assertion(cursor, proposal["redundant_id"])
        validate_execution_contract(proposal, survivor, redundant)
        cursor.execute("""
            UPDATE assertion SET status='superseded', superseded_by=%s WHERE id=%s
        """, (proposal["survivor_id"], proposal["redundant_id"]))
        cursor.execute("""
            INSERT INTO assertion_consolidation_execution (
                proposal_id, survivor_id, redundant_id, action, previous_redundant_status,
                previous_superseded_by, survivor_snapshot, redundant_snapshot, applied_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING *
        """, (proposal_id, proposal["survivor_id"], proposal["redundant_id"], proposal["action"],
                redundant["status"], redundant.get("superseded_by"),
                json.dumps(proposal["survivor_snapshot"], default=str),
                json.dumps(proposal["redundant_snapshot"], default=str), applied_by))
        execution = dict(cursor.fetchone())
        cursor.execute("UPDATE assertion_consolidation_proposal SET applied_at=NOW(), applied_by=%s WHERE id=%s", (applied_by, proposal_id))
        return execution


def reverse_consolidation_execution(execution_id: UUID, *, reversed_by: str, note: str | None = None) -> dict[str, Any] | None:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM assertion_consolidation_execution WHERE id=%s FOR UPDATE", (execution_id,))
        row = cursor.fetchone()
        if not row:
            return None
        execution = dict(row)
        redundant = _locked_assertion(cursor, execution["redundant_id"])
        validate_reversal_contract(execution, redundant)
        cursor.execute("UPDATE assertion SET status=%s, superseded_by=%s WHERE id=%s", (
            execution["previous_redundant_status"], execution.get("previous_superseded_by"), execution["redundant_id"]))
        cursor.execute("""
            UPDATE assertion_consolidation_execution SET reversed_at=NOW(), reversed_by=%s, reversal_note=%s
            WHERE id=%s RETURNING *
        """, (reversed_by, note, execution_id))
        result = dict(cursor.fetchone())
        cursor.execute("UPDATE assertion_consolidation_proposal SET reversed_at=NOW(), reversed_by=%s WHERE id=%s", (reversed_by, execution["proposal_id"]))
        return result
