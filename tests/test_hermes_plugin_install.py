from pathlib import Path

from src.cli import install_hermes_cmd


def test_install_hermes_copies_provider_without_importing_hermes(tmp_path):
    result = install_hermes_cmd(str(tmp_path))
    destination = tmp_path / "plugins" / "openbrain"

    assert result == 0
    assert (destination / "__init__.py").is_file()
    assert (destination / "plugin.yaml").is_file()
    assert (destination / "README.md").is_file()


def test_install_hermes_requires_force_for_existing_plugin(tmp_path):
    destination = tmp_path / "plugins" / "openbrain"
    destination.mkdir(parents=True)
    (destination / "sentinel").write_text("keep", encoding="utf-8")

    assert install_hermes_cmd(str(tmp_path)) == 1
    assert (destination / "sentinel").read_text(encoding="utf-8") == "keep"
    assert install_hermes_cmd(str(tmp_path), force=True) == 0
