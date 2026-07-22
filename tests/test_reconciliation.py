import json

import pytest

from src.providers.reconciliation import JsonlSpoolReconciler


def test_replays_valid_records_and_removes_spool(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"event_type": "session.started"}) + "\n")
    delivered = []

    result = JsonlSpoolReconciler(path).replay(delivered.append)

    assert delivered == [{"event_type": "session.started"}]
    assert result.as_dict() == {
        "replayed": 1,
        "remaining": 0,
        "quarantined": 0,
        "dead_lettered": 0,
    }
    assert not path.exists()


def test_quarantines_malformed_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("not-json\n")

    result = JsonlSpoolReconciler(path).replay(lambda record: None)

    assert result.quarantined == 1
    quarantined = [json.loads(line) for line in (tmp_path / "events.jsonl.quarantine").read_text().splitlines()]
    assert quarantined[0]["raw"] == "not-json"
    assert not path.exists()


def test_failed_delivery_increments_attempts_and_remains(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"event_type": "tool.result"}) + "\n")

    def fail(record):
        raise OSError("offline")

    result = JsonlSpoolReconciler(path, max_attempts=3).replay(fail)

    assert result.remaining == 1
    record = json.loads(path.read_text())
    assert record["attempts"] == 1
    assert record["last_error"] == "OSError"


def test_exhausted_record_moves_to_dead_letter(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"event_type": "tool.result", "attempts": 1}) + "\n")

    with pytest.raises(ValueError):
        JsonlSpoolReconciler(path, max_attempts=0)

    result = JsonlSpoolReconciler(path, max_attempts=2).replay(
        lambda record: (_ for _ in ()).throw(RuntimeError("bad"))
    )

    assert result.dead_lettered == 1
    assert not path.exists()
    dead = json.loads((tmp_path / "events.jsonl.dead").read_text())
    assert dead["attempts"] == 2
    assert dead["last_error"] == "RuntimeError"
