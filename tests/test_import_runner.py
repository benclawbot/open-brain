from __future__ import annotations

from uuid import uuid4

import pytest

from importers.base import ImportAdapter, ImportCandidate, ImportSource, hash_content
from importers.runner import run_import


class StaticAdapter(ImportAdapter):
    def __init__(self, values: list[str], fingerprint: str = "f" * 64):
        self.values = values
        self.fingerprint = fingerprint

    def source_fingerprint(self) -> str:
        return self.fingerprint

    def discover(self):
        return [
            ImportCandidate(
                external_id=f"record-{index}",
                external_hash=hash_content(value),
                source=ImportSource.HERMES_USER_MEMORY,
                content=value,
                record_type="curated_memory_entry",
                authority="curated_memory",
            )
            for index, value in enumerate(self.values, start=1)
        ]


def test_import_runner_dry_run_records_preview(monkeypatch):
    run_id = uuid4()
    recorded = []
    updates = []

    monkeypatch.setattr(
        "importers.runner.create_import_run",
        lambda *args, **kwargs: {"id": run_id},
    )
    monkeypatch.setattr("importers.runner.seen_external_hashes", lambda _: set())
    monkeypatch.setattr(
        "importers.runner.record_import_candidate",
        lambda run, candidate, **kwargs: recorded.append((candidate, kwargs)) or True,
    )
    monkeypatch.setattr(
        "importers.runner.update_import_run",
        lambda run, **kwargs: updates.append(kwargs) or {"id": run},
    )

    result = run_import(
        StaticAdapter(["one", "two"]),
        source_system="hermes.user_memory",
        dry_run=True,
    )

    assert result.run_id == run_id
    assert result.status == "previewed"
    assert result.records_seen == 2
    assert result.records_imported == 2
    assert all(call[1]["operation"] == "preview" for call in recorded)
    assert updates[-1]["status"] == "previewed"


def test_import_runner_non_dry_run_requires_sealing(monkeypatch):
    run_id = uuid4()
    updates = []
    monkeypatch.setattr(
        "importers.runner.create_import_run",
        lambda *args, **kwargs: {"id": run_id},
    )
    monkeypatch.setattr("importers.runner.seen_external_hashes", lambda _: set())
    monkeypatch.setattr("importers.runner.record_import_candidate", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "importers.runner.update_import_run",
        lambda run, **kwargs: updates.append(kwargs) or {"id": run},
    )

    result = run_import(StaticAdapter(["one"]), source_system="hermes.user_memory", dry_run=False)

    assert result.status == "staged"
    assert updates[-1]["status"] == "staged"


def test_import_runner_rejects_resume_after_source_change(monkeypatch):
    run_id = uuid4()
    monkeypatch.setattr(
        "importers.runner.get_import_run",
        lambda _: {
            "id": run_id,
            "status": "running",
            "config": {"dry_run": True, "source_fingerprint": "a" * 64},
        },
    )

    with pytest.raises(ValueError, match="source fingerprint changed"):
        run_import(
            StaticAdapter(["one"], fingerprint="b" * 64),
            source_system="hermes.user_memory",
            resume_run_id=run_id,
        )


def test_import_runner_rejects_sealed_resume(monkeypatch):
    run_id = uuid4()
    monkeypatch.setattr(
        "importers.runner.get_import_run",
        lambda _: {"id": run_id, "status": "sealed", "config": {"dry_run": False}},
    )

    with pytest.raises(ValueError, match="sealed imports cannot be resumed"):
        run_import(
            StaticAdapter(["one"]),
            source_system="hermes.user_memory",
            resume_run_id=run_id,
        )


def test_import_runner_skips_already_recorded_candidate(monkeypatch):
    run_id = uuid4()
    adapter = StaticAdapter(["one"])
    candidate = list(adapter.discover())[0]

    monkeypatch.setattr(
        "importers.runner.create_import_run",
        lambda *args, **kwargs: {"id": run_id},
    )
    monkeypatch.setattr(
        "importers.runner.seen_external_hashes",
        lambda _: {(candidate.external_id, candidate.external_hash)},
    )
    monkeypatch.setattr(
        "importers.runner.record_import_candidate",
        lambda *args, **kwargs: pytest.fail("duplicate candidate should not be recorded"),
    )
    monkeypatch.setattr(
        "importers.runner.update_import_run",
        lambda run, **kwargs: {"id": run},
    )

    result = run_import(adapter, source_system="hermes.user_memory", dry_run=False)

    assert result.status == "staged"
    assert result.records_seen == 1
    assert result.records_imported == 0
    assert result.records_merged == 1