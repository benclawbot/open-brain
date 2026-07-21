from src.context.builder import _item_cost, _select_diverse_candidates
from src.context.models import ContextItem, ContextKind, TrustLabel


def _item(identifier: str, kind: ContextKind, importance: float, text: str = "brief context") -> ContextItem:
    return ContextItem(
        id=identifier,
        kind=kind,
        text=text,
        trust=TrustLabel.TOOL_OBSERVED,
        importance=importance,
    )


def test_diversity_prevents_assertions_from_crowding_out_actionable_kinds():
    candidates = [
        *[_item(f"assertion-{index}", ContextKind.ASSERTION, 1.0 - index / 100) for index in range(8)],
        _item("warning", ContextKind.WARNING, 0.8),
        _item("next", ContextKind.NEXT_ACTION, 0.8),
        _item("decision", ContextKind.DECISION, 0.8),
        _item("task", ContextKind.TASK, 0.8),
    ]

    selected, _, truncated = _select_diverse_candidates(candidates, max_items=5, token_budget=500)

    assert [item.kind for item in selected] == [
        ContextKind.WARNING,
        ContextKind.NEXT_ACTION,
        ContextKind.DECISION,
        ContextKind.TASK,
        ContextKind.ASSERTION,
    ]
    assert truncated is True


def test_remaining_capacity_is_filled_by_global_rank():
    candidates = [
        _item("warning", ContextKind.WARNING, 0.7),
        _item("task", ContextKind.TASK, 0.8),
        _item("assertion-low", ContextKind.ASSERTION, 0.4),
        _item("assertion-high", ContextKind.ASSERTION, 0.95),
        _item("outcome", ContextKind.OUTCOME, 0.6),
    ]

    selected, _, _ = _select_diverse_candidates(candidates, max_items=5, token_budget=500)

    assert [item.id for item in selected] == [
        "warning",
        "task",
        "assertion-high",
        "outcome",
        "assertion-low",
    ]


def test_selection_never_exceeds_token_budget():
    short = _item("warning", ContextKind.WARNING, 1.0, text="short")
    large = _item("decision", ContextKind.DECISION, 1.0, text="x" * 400)
    budget = _item_cost(short)

    selected, used_tokens, truncated = _select_diverse_candidates(
        [short, large],
        max_items=10,
        token_budget=budget,
    )

    assert [item.id for item in selected] == ["warning"]
    assert used_tokens == budget
    assert truncated is True


def test_fresh_item_wins_tie_with_stale_item():
    stale = _item("stale", ContextKind.DECISION, 0.9)
    stale.stale = True
    fresh = _item("fresh", ContextKind.DECISION, 0.9)

    selected, _, _ = _select_diverse_candidates([stale, fresh], max_items=1, token_budget=100)

    assert [item.id for item in selected] == ["fresh"]
