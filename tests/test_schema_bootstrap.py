from importlib.resources import files


def test_base_schema_is_packaged_as_first_migration() -> None:
    migration = files("src.db.migrations").joinpath("001_base_schema.sql")
    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS memory" in sql
    assert "CREATE EXTENSION IF NOT EXISTS \"vector\"" in sql


def test_migrate_command_applies_packaged_migrations(monkeypatch, capsys) -> None:
    from src.cli import migrate_cmd
    from src.db import migrate

    monkeypatch.setattr(
        migrate,
        "apply_migrations",
        lambda: ["001_base_schema.sql", "002_continuity_foundation.sql"],
    )

    assert migrate_cmd() == 0
    output = capsys.readouterr().out
    assert "001_base_schema.sql" in output
    assert "002_continuity_foundation.sql" in output


def test_migrate_command_reports_failure(monkeypatch, capsys) -> None:
    from src.cli import migrate_cmd
    from src.db import migrate

    def fail() -> list[str]:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(migrate, "apply_migrations", fail)

    assert migrate_cmd() == 1
    assert "database unavailable" in capsys.readouterr().err
