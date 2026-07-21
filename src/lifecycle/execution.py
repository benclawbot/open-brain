"""Guarded assertion lifecycle execution with stale-snapshot validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ALLOWED_TARGETS = {"dormant", "archived"}
_SNAPSHOT_FIELDS = (
    "status",
    "predicate",
    "value",
    "authority",
    "confidence",
    "importance",
    "access_count",
    "useful_count",
    "harmful_count",
)


class LifecycleExecutionError(ValueError):
    """Raised when a proposal cannot be safely applied or reversed."""


@dataclass(frozen=True, slots=True)
class SnapshotComparison:
    matches: bool
    changed_fields: tuple[str, ...]


def compare_assertion_snapshot(current: dict[str, Any], snapshot: dict[str, Any]) -> SnapshotComparison:
    """Compare only fields captured by the proposal's immutable assertion snapshot."""
    changed = tuple(field for field in _SNAPSHOT_FIELDS if current.get(field) != snapshot.get(field))
    return SnapshotComparison(matches=not changed, changed_fields=changed)


def validate_execution_contract(proposal: dict[str, Any], current_assertion: dict[str, Any]) -> str:
    """Validate review state, target transition, and snapshot freshness."""
    if proposal.get("state") != "accepted":
        raise LifecycleExecutionError("proposal must be accepted before execution")
    if proposal.get("applied_at") is not None:
        raise LifecycleExecutionError("proposal has already been applied")

    target = proposal.get("target_status")
    if target not in _ALLOWED_TARGETS:
        raise LifecycleExecutionError("only dormant and archived target statuses may be applied")
    if current_assertion.get("status") == "confirmed":
        raise LifecycleExecutionError("confirmed assertions cannot be demoted or archived")
    if current_assertion.get("status") in {"deleted", "superseded"}:
        raise LifecycleExecutionError("terminal assertions cannot be changed by lifecycle execution")

    comparison = compare_assertion_snapshot(current_assertion, proposal.get("assertion_snapshot") or {})
    if not comparison.matches:
        fields = ", ".join(comparison.changed_fields)
        raise LifecycleExecutionError(f"assertion changed since proposal generation: {fields}")
    return target


def validate_reversal_contract(execution: dict[str, Any], current_assertion: dict[str, Any]) -> str:
    """Validate one-step reversal without overwriting later assertion changes."""
    if execution.get("reversed_at") is not None:
        raise LifecycleExecutionError("execution has already been reversed")
    if current_assertion.get("status") != execution.get("applied_status"):
        raise LifecycleExecutionError("assertion status changed after lifecycle execution")
    previous = execution.get("previous_status")
    if not previous:
        raise LifecycleExecutionError("execution has no previous status to restore")
    return str(previous)
