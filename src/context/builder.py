"""Build compact, trust-labelled context packets for agent consumption."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from context.models import ContextItem, ContextKind, ContextPacket, ContextRequest, TrustLabel
from db.context_queries import fetch_structured_context, get_scope_revisions


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _trust(authority: str | None, status: str | None = None, stale: bool = False) -> TrustLabel:
    if status == "contradicted":
        return TrustLabel.CONTRADICTED
    if stale:
        return TrustLabel.STALE
    mapping = {
        "user_confirmed": TrustLabel.USER_CONFIRMED,
        "tool_observed": TrustLabel.TOOL_OBSERVED,
        "curated_memory": TrustLabel.CURATED_MEMORY,
    }
    return mapping.get(authority or "", TrustLabel.INFERRED)


def _is_stale(value: datetime | None, days: int = 30) -> bool:
    if value is None:
        return False
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (now - value).days >= days


def build_context_packet(request: ContextRequest) -> ContextPacket:
    raw = fetch_structured_context(
        request.project_id,
        request.task_id,
        request.include_history,
        request.max_items,
    )
    candidates: list[ContextItem] = []

    project = raw.get("project")
    if project:
        text = f"{project['name']}: {project.get('goal') or 'No goal recorded'} (status: {project['status']})"
        candidates.append(ContextItem(id=project["id"], kind=ContextKind.PROJECT, text=text, trust=TrustLabel.TOOL_OBSERVED, importance=1.0))

    for task in raw.get("tasks", []):
        text = f"{task['title']} (status: {task['status']})"
        if task.get("goal"):
            text += f" — {task['goal']}"
        candidates.append(ContextItem(id=task["id"], kind=ContextKind.TASK, text=text, trust=TrustLabel.TOOL_OBSERVED, importance=0.9, observed_at=task.get("updated_at")))
        if task.get("next_action"):
            candidates.append(ContextItem(id=f"task-next:{task['id']}", kind=ContextKind.NEXT_ACTION, text=task["next_action"], trust=TrustLabel.TOOL_OBSERVED, importance=0.95, observed_at=task.get("updated_at")))
        for blocker in task.get("blockers") or []:
            candidates.append(ContextItem(id=f"task-blocker:{task['id']}:{len(candidates)}", kind=ContextKind.WARNING, text=str(blocker), trust=TrustLabel.TOOL_OBSERVED, importance=1.0, observed_at=task.get("updated_at")))

    for decision in raw.get("decisions", []):
        candidates.append(ContextItem(id=decision["id"], kind=ContextKind.DECISION, text=decision["statement"], trust=TrustLabel.USER_CONFIRMED, importance=0.95, observed_at=decision.get("decided_at"), stale=decision.get("status") != "active"))

    for assertion in raw.get("assertions", []):
        observed_at = assertion.get("last_confirmed_at") or assertion.get("last_observed_at")
        stale = _is_stale(observed_at, 90 if assertion.get("temporal_class") == "stable" else 30)
        value = assertion.get("value")
        text = f"{assertion['predicate']}: {value}"
        candidates.append(ContextItem(id=assertion["id"], kind=ContextKind.ASSERTION, text=text, trust=_trust(assertion.get("metadata", {}).get("authority") if isinstance(assertion.get("metadata"), dict) else None, assertion.get("status"), stale), importance=float(assertion.get("importance", 0.5)), observed_at=observed_at, stale=stale))

    for outcome in raw.get("outcomes", []):
        result = outcome.get("result") or outcome.get("objective") or "Outcome recorded"
        prefix = "Succeeded" if outcome.get("success") else "Failed" if outcome.get("success") is False else "Outcome"
        candidates.append(ContextItem(id=outcome["id"], kind=ContextKind.OUTCOME, text=f"{prefix}: {result}", trust=TrustLabel.TOOL_OBSERVED, importance=0.7, observed_at=outcome.get("occurred_at")))

    candidates.sort(key=lambda item: (item.importance, not item.stale), reverse=True)
    selected: list[ContextItem] = []
    used_tokens = 0
    truncated = False
    for item in candidates:
        cost = _estimate_tokens(item.text) + 8
        if len(selected) >= request.max_items or used_tokens + cost > request.token_budget:
            truncated = True
            continue
        selected.append(item)
        used_tokens += cost

    revisions = get_scope_revisions(request.user_identity_id, request.project_id, request.task_id)
    return ContextPacket(
        packet_id=uuid4(),
        scope_revisions=revisions,
        items=selected,
        estimated_tokens=used_tokens,
        truncated=truncated,
    )
