import pytest

from src.importers.path_guard import ImportPathError, import_roots, resolve_import_path


def test_accepts_markdown_inside_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    source = root / "MEMORY.md"
    source.write_text("# memory\n", encoding="utf-8")
    monkeypatch.setenv("OPENBRAIN_IMPORT_ROOTS", str(root))

    assert resolve_import_path(str(source)) == source.resolve()


def test_rejects_path_outside_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    outside = tmp_path / "notes.md"
    outside.write_text("secret\n", encoding="utf-8")
    monkeypatch.setenv("OPENBRAIN_IMPORT_ROOTS", str(root))

    with pytest.raises(ImportPathError) as excinfo:
        resolve_import_path(str(outside))

    assert excinfo.value.status_code == 403


def test_rejects_non_document_files_even_inside_root(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    private_key = root / "id_rsa"
    private_key.write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    monkeypatch.setenv("OPENBRAIN_IMPORT_ROOTS", str(root))

    with pytest.raises(ImportPathError) as excinfo:
        resolve_import_path(str(private_key))

    assert excinfo.value.status_code == 415


def test_rejects_missing_file(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    monkeypatch.setenv("OPENBRAIN_IMPORT_ROOTS", str(root))

    with pytest.raises(ImportPathError) as excinfo:
        resolve_import_path(str(root / "missing.md"))

    assert excinfo.value.status_code == 404


def test_rejects_parent_traversal(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")
    monkeypatch.setenv("OPENBRAIN_IMPORT_ROOTS", str(root))

    with pytest.raises(ImportPathError):
        resolve_import_path(str(root / ".." / "outside.md"))


def test_default_roots_cover_agent_homes(monkeypatch):
    monkeypatch.delenv("OPENBRAIN_IMPORT_ROOTS", raising=False)

    roots = import_roots()

    names = {root.name for root in roots}
    assert {".hermes", ".codex", ".claude"} <= names
