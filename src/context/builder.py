"""Build compact, trust-labelled context packets for agent consumption."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

try:
    from .cache import cache_key, load_cached_packet, store_cached_packet
    from .models import ContextItem, ContextKind, ContextPacket, ContextRequest, TrustLabel
    from ..db.compaction_queries import fetch_active_compactions
    from ..db.context_queries import fetch_structured_context, get_scope_revisions
except ImportError:
    from context.cache import cache_key, load_cached_packet, store_cached_packet
    from context.models import ContextItem, ContextKind, ContextPacket, ContextRequest, TrustLabel
    from db.compaction_queries import fetch_active_compactions
    from db.context_queries import fetch_structured_context, get_scope_revisions

_DIVERSITY_ORDER = (
    ContextKind.WARNING, ContextKind.NEXT_ACTION, ContextKind.DECISION,
    ContextKind.TASK, ContextKind.ASSERTION, ContextKind.PROJECT, ContextKind.OUTCOME,
)


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _item_cost(item: ContextItem) -> int:
    return _estimate_tokens(item.text) + 8


def _trust(authority: str | None, status: str | None = None, stale: bool = False) -> TrustLabel:
    if status == "contradicted":
        return TrustLabel.CONTRADICTED
    if stale:
        return TrustLabel.STALE
    return {
        "user_confirmed": TrustLabel.USER_CONFIRMED,
        "tool_observed": TrustLabel.TOOL_OBSERVED,
        "curated_memory": TrustLabel.CURATED_MEMORY,
    }.get(authority or "", TrustLabel.INFERRED)


def _is_stale(value: datetime | None, days: int = 30) -> bool:
    if value is None:
        return False
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (now - value).days >= days


def _candidate_rank(item: ContextItem) -> tuple[float, bool]:
    return item.importance, not item.stale


def _select_diverse_candidates(candidates: list[ContextItem], max_items: int,
                               token_budget: int) -> tuple[list[ContextItem], int, bool]:
    ranked = sorted(candidates, key=_candidate_rank, reverse=True)
    selected: list[ContextItem] = []
    selected_ids: set[str] = set()
    used_tokens = 0

    def add(item: ContextItem) -> bool:
        nonlocal used_tokens
        key = str(item.id)
        cost = _item_cost(item)
        if key in selected_ids or len(selected) >= max_items or used_tokens + cost > token_budget:
            return False
        selected.append(item)
        selected_ids.add(key)
        used_tokens += cost
        return True

    by_kind: dict[ContextKind, list[ContextItem]] = {}
    for item in ranked:
        by_kind.setdefault(item.kind, []).append(item)
    for kind in _DIVERSITY_ORDER:
        for item in by_kind.get(kind, []):
            if add(item):
                break
    for item in ranked:
        add(item)
    return selected, used_tokens, len(selected) < len(candidates)


def build_context_packet(request: ContextRequest) -> ContextPacket:
    revisions = get_scope_revisions(request.user_identity_id, request.project_id, request.task_id)
    key = cache_key(request, revisions)
    cached = load_cached_packet(key)
    if cached is not None:
        return cached

    raw = fetch_structured_context(request.project_id, request.task_id,
                                   request.include_history, request.max_items)
    candidates: list[ContextItem] = []
    project = raw.get("project")
    if project:
        text = f"{project['name']}: {project.get('goal') or 'No goal recorded'} (status: {project['status']})"
        candidates.append(ContextItem(id=project["id"], kind=ContextKind.PROJECT, text=text,
                                      trust=TrustLabel.TOOL_OBSERVED, importance=1.0))
    for task in raw.get("tasks", []):
        text = f"{task['title']} (status: {task['status']})"
        if task.get("goal"):
            text += f" — {task['goal']}"
        candidates.append(ContextItem(id=task["id"], kind=ContextKind.TASK, text=text,
                                      trust=TrustLabel.TOOL_OBSERVED, importance=0.9,
                                      observed_at=task.get("updated_at")))
        if task.get("next_action"):
            candidates.append(ContextItem(id=f"task-next:{task['id']}", kind=ContextKind.NEXT_ACTION,
                                          text=task["next_action"], trust=TrustLabel.TOOL_OBSERVED,
                                          importance=0.95, observed_at=task.get("updated_at")))
        for blocker in task.get("blockers") or []:
            candidates.append(ContextItem(id=f"task-blocker:{task['id']}:{len(candidates)}",
                                          kind=ContextKind.WARNING, text=str(blocker),
                                          trust=TrustLabel.TOOL_OBSERVED, importance=1.0,
                                          observed_at=task.get("updated_at")))
    for decision in raw.get("decisions", []):
        candidates.append(ContextItem(id=decision["id"], kind=ContextKind.DECISION,
                                      text=decision["statement"], trust=TrustLabel.USER_CONFIRMED,
                                      importance=0.95, observed_at=decision.get("decided_at"),
                                      stale=decision.get("status") != "active"))
    for assertion in raw.get("assertions", []):
        observed_at = assertion.get("last_confirmed_at") or assertion.get("last_observed_at")
        stale = _is_stale(observed_at, 90 if assertion.get("temporal_class") == "stable" else 30)
        candidates.append(ContextItem(id=assertion["id"], kind=ContextKind.ASSERTION,
                                      text=f"{assertion['predicate']}: {assertion.get('value')}",
                                      trust=_trust(None, assertion.get("status"), stale),
                                      importance=float(assertion.get("importance", 0.5)),
                                      observed_at=observed_at, stale=stale))
    for outcome in raw.get("outcomes", []):
        result = outcome.get("result") or outcome.get("objective") or "Outcome recorded"
        prefix = "Succeeded" if outcome.get("success") else "Failed" if outcome.get("success") is False else "Outcome"
        candidates.append(ContextItem(id=outcome["id"], kind=ContextKind.OUTCOME,
                                      text=f"{prefix}: {result}", trust=TrustLabel.TOOL_OBSERVED,
                                      importance=0.7, observed_at=outcome.get("occurred_at")))

    # Only the active rollup is retrieved. Its raw source events remain available by
    # provenance ID, but are intentionally not emitted beside the summary.
    for rollup in fetch_active_compactions(project_id=request.project_id, task_id=request.task_id,
                                           limit=request.max_items):
        candidates.append(ContextItem(
            id=f"compaction:{rollup['id']}", kind=ContextKind.ASSERTION,
            text=rollup["summary"], trust=TrustLabel.CURATED_MEMORY, importance=0.65,
            observed_at=rollup.get("last_occurred_at"),
            metadata={"derived": True, "source_event_count": rollup["source_event_count"],
                      "source_fingerprint": rollup["source_fingerprint"],
                      "policy_version": rollup["policy_version"]},
        ))

    selected, used_tokens, truncated = _select_diverse_candidates(
        candidates, request.max_items, request.token_budget)
    packet = ContextPacket(packet_id=uuid4(), scope_revisions=revisions, items=selected,
                           estimated_tokens=used_tokens, truncated=truncated)
    store_cached_packet(key, request, revisions, packet)
    return packet
