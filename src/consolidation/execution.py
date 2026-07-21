"""Safety contracts for applying and reversing assertion consolidation."""

from __future__ import annotations

from typing import Any

TERMINAL = {"deleted", "archived", "superseded"}


def comparable_snapshot(assertion: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(assertion["id"]),
        "subject_type": assertion["subject_type"],
        "subject_id": str(assertion["subject_id"]) if assertion.get("subject_id") else None,
        "predicate": assertion["predicate"],
        "value": assertion["value"],
        "status": assertion["status"],
        "authority": float(assertion["authority"]),
        "confidence": float(assertion["confidence"]),
        "importance": float(assertion["importance"]),
        "useful_count": int(assertion["useful_count"]),
        "harmful_count": int(assertion["harmful_count"]),
        "supporting_evidence_count": int(assertion.get("supporting_evidence_count") or 0),
        "contradicting_evidence_count": int(assertion.get("contradicting_evidence_count") or 0),
        "last_observed_at": assertion["last_observed_at"].isoformat() if assertion.get("last_observed_at") else None,
        "last_confirmed_at": assertion["last_confirmed_at"].isoformat() if assertion.get("last_confirmed_at") else None,
    }


def validate_execution_contract(proposal: dict[str, Any], survivor: dict[str, Any], redundant: dict[str, Any]) -> None:
    if proposal["state"] != "accepted":
        raise ValueError("consolidation proposal must be accepted")
    if proposal.get("applied_at"):
        raise ValueError("consolidation proposal was already applied")
    if proposal["action"] not in {"duplicate", "supersede"}:
        raise ValueError("unsupported consolidation action")
    if str(survivor["id"]) == str(redundant["id"]):
        raise ValueError("survivor and redundant assertion must differ")
    if survivor["status"] in TERMINAL or redundant["status"] in TERMINAL:
        raise ValueError("terminal assertions cannot be consolidated")
    if comparable_snapshot(survivor) != proposal["survivor_snapshot"]:
        raise ValueError("survivor assertion changed after proposal generation")
    if comparable_snapshot(redundant) != proposal["redundant_snapshot"]:
        raise ValueError("redundant assertion changed after proposal generation")


def validate_reversal_contract(execution: dict[str, Any], redundant: dict[str, Any]) -> None:
    if execution.get("reversed_at"):
        raise ValueError("consolidation execution was already reversed")
    if redundant["status"] != "superseded":
        raise ValueError("redundant assertion changed after consolidation")
    if str(redundant.get("superseded_by")) != str(execution["survivor_id"]):
        raise ValueError("assertion lineage changed after consolidation")
