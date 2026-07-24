"""Tests for safe bootstrap import of Hermes markdown memory."""

from src.importers.base import ImportSource, hash_content
from src.importers.hermes_markdown import HermesMarkdownImporter, discover_default_hermes_memory


def test_importer_preserves_sections_authority_and_hashes(tmp_path):
    path = tmp_path / "USER.md"
    path.write_text(
        "# Preferences\n\n- Use upstream Hermes.\n- Keep memory model-independent.\n\n"
        "## Notes\nThis paragraph is contextual.\n",
        encoding="utf-8",
    )

    records = list(
        HermesMarkdownImporter(path, ImportSource.HERMES_USER_MEMORY).discover()
    )

    assert [record.content for record in records] == [
        "Use upstream Hermes.",
        "Keep memory model-independent.",
        "This paragraph is contextual.",
    ]
    assert records[0].authority == "curated_memory"
    assert records[0].record_type == "curated_memory_entry"
    assert records[0].metadata["section"] == "Preferences"
    assert records[2].metadata["section"] == "Notes"
    assert records[0].external_hash == hash_content("Use upstream Hermes.")


def test_import_ids_are_deterministic(tmp_path):
    path = tmp_path / "MEMORY.md"
    path.write_text("# Decisions\n- Use Open Brain as system of record.\n", encoding="utf-8")

    first = list(
        HermesMarkdownImporter(path, ImportSource.HERMES_AGENT_MEMORY).discover()
    )
    second = list(
        HermesMarkdownImporter(path, ImportSource.HERMES_AGENT_MEMORY).discover()
    )

    assert first[0].external_id == second[0].external_id
    assert first[0].external_hash == second[0].external_hash


def test_default_discovery_tolerates_missing_files(tmp_path):
    assert discover_default_hermes_memory(tmp_path) == []


def test_importer_does_not_treat_headings_as_memories(tmp_path):
    path = tmp_path / "USER.md"
    path.write_text("# Preferences\n## Communication\n", encoding="utf-8")
    records = list(
        HermesMarkdownImporter(path, ImportSource.HERMES_USER_MEMORY).discover()
    )
    assert records == []
