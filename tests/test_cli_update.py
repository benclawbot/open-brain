from src.cli import update_cmd


def test_update_reports_non_pipx_installation(monkeypatch):
    monkeypatch.setattr(
        "src.cli._run",
        lambda command: (_ for _ in ()).throw(FileNotFoundError("pipx")),
    )
    assert update_cmd(skip_migrations=True) == 1


def test_update_skip_migrations_succeeds(monkeypatch):
    commands = []
    monkeypatch.setattr("src.cli._run", lambda command: commands.append(command))
    assert update_cmd(skip_migrations=True) == 0
    assert commands == [["pipx", "upgrade", "openbrain"]]
