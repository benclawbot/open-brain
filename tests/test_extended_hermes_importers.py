from __future__ import annotations

import json

import pytest

from src.importers.hermes_context import discover_allowlisted_context
from src.importers.hermes_operations import HermesCronImporter, HermesSkillImporter
from src.importers.hermes_sessions import HermesSessionImporter


def test_context_import_requires_allowlist_and_blocks_escape(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "PROJECT.md").write_text("# Project\n- Use upstream Hermes", encoding="utf-8")

    candidates = discover_allowlisted_context(home, ["PROJECT.md"])
    assert len(candidates) == 1
    assert candidates[0].metadata["allowlisted"] is True

    with pytest.raises(ValueError, match="escapes Hermes home"):
        discover_allowlisted_context(home, ["../secret.txt"])


def test_session_import_prefers_summary_over_transcript(tmp_path):
    source = tmp_path / "sessions.json"
    source.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "session_id": "s1",
                        "summary": "Decided to use upstream Hermes.",
                        "messages": [{"role": "user", "content": "hello"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    candidates = list(HermesSessionImporter(source).discover())
    assert len(candidates) == 1
    assert candidates[0].record_type == "session_summary"
    assert candidates[0].metadata["episodic"] is True


def test_skill_import_is_procedural_and_requires_evaluation(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "review.md").write_text("# Review\nRun tests before merge.", encoding="utf-8")

    candidates = list(HermesSkillImporter(skills).discover())
    assert candidates[0].record_type == "procedure"
    assert candidates[0].metadata["requires_evaluation_before_activation"] is True


def test_cron_import_keeps_hermes_as_executor(tmp_path):
    source = tmp_path / "cron.json"
    source.write_text(
        json.dumps({"jobs": [{"id": "daily", "schedule": "0 8 * * *", "prompt": "brief"}]}),
        encoding="utf-8",
    )

    candidates = list(HermesCronImporter(source).discover())
    assert candidates[0].record_type == "automation"
    assert candidates[0].metadata["executor"] == "hermes"
