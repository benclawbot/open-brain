"""Persistence and guarded execution for assertion pruning."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from .connection import get_db_cursor
from ..pruning.assertions import PruningCandidate, propose_pruning
from ..pruning.execution import validate_archive_contract, validate_restore_contract

POLICY_VERSION = "assertion-pruning-v1"


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]), "status": row["status"],
        "temporal_class": row["temporal_class"],
        "authority": float(row["authority"]), "confidence": float(row["confidence"]),
        "importance": float(row["importance"]), "access_count": int(row["access_count"]),
        "useful_count": int(row["useful_count"]), "harmful_count": int(row["harmful_count"]),
        "last_observed_at": row["last_observed_at"].isoformat() if row.get("last_observed_at") else None,
        "last_accessed_at": row["last_accessed_at"].isoformat() if row.get("last_accessed_at") else None,
        "valid_until": row["valid_until"].isoformat() if row.get("valid_until") else None,
        "superseded_by": str(row["superseded_by"]) if row.get("superseded_by") else None,
        "evidence_count": int(row.get("evidence_count") or 0),
    }


def _candidate(row: dict[str, Any]) -> PruningCandidate:
    return PruningCandidate(
        assertion_id=str(row["id"]), status=row["status"], temporal_class=row["temporal_class"],
        authority=float(row["authority"]), confidence=float(row["confidence"]),
        importance=float(row["importance"]), access_count=int(row["access_count"]),
        useful_count=int(row["useful_count"]), harmful_count=int(row["harmful_count"]),
        evidence_count=int(row.get("evidence_count") or 0), last_observed_at=row["last_observed_at"],
        last_accessed_at=row.get("last_accessed_at"), valid_until=row.get("valid_until"),
        superseded_by=str(row["superseded_by"]) if row.get("superseded_by") else None,
    )


def generate_pruning_proposals(*, limit: int = 500) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT a.*, COUNT(e.id) AS evidence_count
            FROM assertion a LEFT JOIN assertion_evidence e ON e.assertion_id=a.id
            WHERE a.status NOT IN ('archived','deleted')
            GROUP BY a.id ORDER BY a.last_observed_at ASC LIMIT %s
        """, (limit,))
        for raw in cursor.fetchall():
            row = dict(raw)
            proposal = propose_pruning(_candidate(row))
            if proposal is None:
                continue
            snapshot = _snapshot(row)
            payload = {"snapshot": snapshot, "reason": proposal.reason.value,
                       "score": proposal.score, "retention_days": proposal.retention_days,
                       "policy_version": POLICY_VERSION}
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            cursor.execute("""
                INSERT INTO assertion_pruning_proposal (
                    assertion_id, reason, score, retention_days, assertion_snapshot, fingerprint
                ) VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                ON CONFLICT (assertion_id, fingerprint) DO NOTHING RETURNING *
            """, (row["id"], proposal.reason.value, proposal.score, proposal.retention_days,
                    json.dumps(snapshot), fingerprint))
            inserted = cursor.fetchone()
            if inserted:
                created.append(dict(inserted))
    return created


def list_pruning_proposals(*, state: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT p.*, a.subject_type, a.subject_id, a.predicate, a.value
            FROM assertion_pruning_proposal p JOIN assertion a ON a.id=p.assertion_id
            WHERE p.state=%s ORDER BY p.score DESC, p.created_at ASC LIMIT %s
        """, (state, limit))
        return [dict(row) for row in cursor.fetchall()]


def review_pruning_proposal(proposal_id: UUID, *, state: str, reviewed_by: str,
                            note: str | None = None) -> dict[str, Any] | None:
    if state not in {"accepted", "rejected"}:
        raise ValueError("state must be accepted or rejected")
    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE assertion_pruning_proposal
            SET state=%s, reviewed_by=%s, review_note=%s, reviewed_at=NOW()
            WHERE id=%s AND state='pending' RETURNING *
        """, (state, reviewed_by, note, proposal_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def _locked_assertion(cursor: Any, assertion_id: UUID) -> dict[str, Any]:
    cursor.execute("""
        SELECT a.*, (SELECT COUNT(*) FROM assertion_evidence e WHERE e.assertion_id=a.id) AS evidence_count
        FROM assertion a WHERE a.id=%s FOR UPDATE
    """, (assertion_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError("assertion not found")
    return dict(row)


def apply_pruning_proposal(proposal_id: UUID, *, applied_by: str) -> dict[str, Any] | None:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM assertion_pruning_proposal WHERE id=%s FOR UPDATE", (proposal_id,))
        raw = cursor.fetchone()
        if not raw:
            return None
        proposal = dict(raw)
        current = _locked_assertion(cursor, proposal["assertion_id"])
        validate_archive_contract(proposal, _snapshot(current))
        cursor.execute("UPDATE assertion SET status='archived' WHERE id=%s", (proposal["assertion_id"],))
        cursor.execute("""
            INSERT INTO assertion_tombstone (
                proposal_id, assertion_id, previous_status, assertion_snapshot,
                evidence_count, reason, retention_until, applied_by
            ) VALUES (%s,%s,%s,%s::jsonb,%s,%s,NOW()+(%s * INTERVAL '1 day'),%s)
            RETURNING *
        """, (proposal_id, proposal["assertion_id"], current["status"],
                json.dumps(proposal["assertion_snapshot"]), current["evidence_count"],
                proposal["reason"], proposal["retention_days"], applied_by))
        tombstone = dict(cursor.fetchone())
        cursor.execute("""
            UPDATE assertion_pruning_proposal SET state='applied', applied_at=NOW(), applied_by=%s
            WHERE id=%s
        """, (applied_by, proposal_id))
        return tombstone


def restore_tombstone(tombstone_id: UUID, *, reversed_by: str,
                      note: str | None = None) -> dict[str, Any] | None:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM assertion_tombstone WHERE id=%s FOR UPDATE", (tombstone_id,))
        raw = cursor.fetchone()
        if not raw:
            return None
        tombstone = dict(raw)
        current = _locked_assertion(cursor, tombstone["assertion_id"])
        validate_restore_contract(tombstone, _snapshot(current))
        cursor.execute("UPDATE assertion SET status=%s WHERE id=%s",
                       (tombstone["previous_status"], tombstone["assertion_id"]))
        cursor.execute("""
            UPDATE assertion_tombstone SET reversed_by=%s, reversed_at=NOW(), reversal_note=%s
            WHERE id=%s RETURNING *
        """, (reversed_by, note, tombstone_id))
        restored = dict(cursor.fetchone())
        cursor.execute("UPDATE assertion_pruning_proposal SET state='reversed' WHERE id=%s",
                       (tombstone["proposal_id"],))
        return restored
