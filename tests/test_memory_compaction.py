from datetime import datetime, timezone

from src.compaction.engine import (
    CompactionCandidate,
    build_summary,
    event_fingerprint,
    source_fingerprint,
)

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def candidate(identifier: str, message: str) -> CompactionCandidate:
    return CompactionCandidate(
        event_id=identifier,
        event_type="task.updated",
        payload={"message": message},
        occurred_at=NOW,
    )


def test_source_fingerprint_is_order_independent():
    left = candidate("a", "first")
    right = candidate("b", "second")
    assert source_fingerprint([left, right]) == source_fingerprint([right, left])


def test_source_fingerprint_changes_when_source_changes():
    original = candidate("a", "first")
    changed = candidate("a", "changed")
    assert event_fingerprint(original) != event_fingerprint(changed)
    assert source_fingerprint([original]) != source_fingerprint([changed])


def test_summary_deduplicates_repetitive_payloads_but_preserves_count():
    rows = [candidate("a", "same"), candidate("b", "same"), candidate("c", "new")]
    summary = build_summary(rows)
    assert summary.startswith("3 task.updated events")
    assert summary.count("same") == 1
    assert "new" in summary


def test_summary_requires_sources():
    import pytest

    with pytest.raises(ValueError, match="source event"):
        build_summary([])
