from __future__ import annotations

import asyncio
import json
import os
import py_compile
import re
import shlex
import subprocess
import sys
from pathlib import Path
import tomllib

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


def test_shipped_sandbox_modules_compile() -> None:
    for relative_path in ("src/sandbox/__init__.py", "src/sandbox/docker_sandbox.py"):
        py_compile.compile(str(ROOT / relative_path), doraise=True)


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    (
        ("src.sandbox", "SandboxExecutor"),
        ("src.sandbox.docker_sandbox", "DockerSandbox"),
    ),
)
def test_sandbox_python_runner_preserves_arbitrary_code(
    module_name: str,
    class_name: str,
) -> None:
    module = __import__(module_name, fromlist=[class_name])
    sandbox = getattr(module, class_name)()
    captured: dict[str, object] = {}

    async def capture(command: str, timeout: int | None = None):
        captured["command"] = command
        captured["timeout"] = timeout
        return None

    sandbox.run = capture
    code = "print(\"quotes: 'single' and \\\\ backslash\")"
    asyncio.run(sandbox.run_python(code, timeout=17))

    assert shlex.split(str(captured["command"])) == ["python3", "-c", code]
    assert captured["timeout"] == 17


def test_api_uses_distribution_version_without_duplicate_namespace() -> None:
    script = """
import json
import sys
from src.api.main import app
print(json.dumps({
    "version": app.version,
    "duplicate_api_namespace": any(
        name == "api" or name.startswith("api.") for name in sys.modules
    ),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["version"] == project_version()
    assert payload["duplicate_api_namespace"] is False


def test_setup_saves_complete_env_in_project_root_without_yaml_secrets(
    tmp_path: Path,
) -> None:
    from src.setup import save_configuration

    config = {
        "database": {
            "host": "database.internal",
            "port": 5432,
            "name": "openbrain",
            "user": "brain",
            "password": "database-secret",
        },
        "embedder": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimensions": 1536,
        },
        "llm": {"provider": "ollama", "model": "llama3"},
        "api": {"host": "127.0.0.1", "port": 8000, "cors_origins": []},
        "mcp": {"transport": "stdio"},
        "dashboard": {"port": 8501},
        "security": {"mode": "direct"},
        "analytics": {
            "notifications": {
                "telegram": {"enabled": True, "bot_token": "telegram-secret"},
            },
        },
    }

    config_path, env_path = save_configuration(
        config,
        project_root=tmp_path,
        environment={"OPENAI_API_KEY": "provider-secret"},
    )

    assert config_path == tmp_path / "config" / "settings.yaml"
    assert env_path == tmp_path / ".env"

    env_text = env_path.read_text(encoding="utf-8")
    assert "DB_HOST=database.internal" in env_text
    assert "DB_PORT=5432" in env_text
    assert "DB_NAME=openbrain" in env_text
    assert "DB_USER=brain" in env_text
    assert "DB_PASSWORD=database-secret" in env_text
    assert "API_PORT=8000" in env_text
    assert "DASHBOARD_PORT=8501" in env_text
    assert "SECURITY_MODE=direct" in env_text
    assert "OPENAI_API_KEY=provider-secret" in env_text
    generated_key = re.search(r"^OPENBRAIN_API_KEY=(.+)$", env_text, re.MULTILINE)
    assert generated_key
    assert len(generated_key.group(1)) >= 32
    assert "MCP_PORT" not in env_text

    saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "password" not in saved_config["database"]
    assert "bot_token" not in saved_config["analytics"]["notifications"]["telegram"]


def test_install_configuration_generates_and_reuses_transparent_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.runtime_config import configure_runtime_environment

    config_home = tmp_path / "user-config"
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env.example").write_text(
        "DB_PASSWORD=openbrain\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENBRAIN_CONFIG_DIR", str(config_home))
    monkeypatch.delenv("OPENBRAIN_API_KEY", raising=False)

    project_env = configure_runtime_environment(project_root=project_root)
    first_key = re.search(
        r"^OPENBRAIN_API_KEY=(.+)$",
        project_env.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert first_key
    assert len(first_key.group(1)) >= 32
    assert "OPENBRAIN_AUTH_REQUIRED=true" in project_env.read_text(encoding="utf-8")
    generated_db_password = re.search(
        r"^DB_PASSWORD=(.+)$",
        project_env.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert generated_db_password
    assert len(generated_db_password.group(1)) >= 24

    user_env = config_home / ".env"
    assert user_env.is_file()
    assert f"OPENBRAIN_API_KEY={first_key.group(1)}" in user_env.read_text(encoding="utf-8")

    monkeypatch.delenv("OPENBRAIN_API_KEY", raising=False)
    configure_runtime_environment(project_root=project_root)
    second_key = re.search(
        r"^OPENBRAIN_API_KEY=(.+)$",
        project_env.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert second_key
    assert second_key.group(1) == first_key.group(1)

    if os.name != "nt":
        assert oct(project_env.stat().st_mode & 0o777) == "0o600"
        assert oct(user_env.stat().st_mode & 0o777) == "0o600"


def test_compose_requires_database_secret_and_binds_postgres_locally() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "DB_PASSWORD: openbrain" not in compose
    assert "POSTGRES_PASSWORD: openbrain" not in compose
    assert compose.count("${DB_PASSWORD:?") == 3
    assert '127.0.0.1:${DB_HOST_PORT:-5433}:5432' in compose


def test_migration_sequence_rejects_new_duplicate_numbers() -> None:
    from src.db.migrate import validate_migration_sequence

    current = sorted(path.name for path in (ROOT / "src/db/migrations").glob("*.sql"))
    validate_migration_sequence(current)

    with pytest.raises(RuntimeError, match="duplicate migration sequence 099"):
        validate_migration_sequence(["099_first.sql", "099_second.sql"])


def test_runtime_and_hermes_plugin_versions_match_distribution() -> None:
    import src

    plugin = yaml.safe_load(
        (ROOT / "src/openbrain_hermes_plugin/plugin.yaml").read_text(encoding="utf-8")
    )
    assert src.__version__ == project_version()
    assert plugin["version"] == project_version()


def test_generated_distribution_metadata_is_not_tracked_as_source() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "openbrain.egg-info"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert not tracked.strip()


def test_ci_compiles_all_modules_and_runs_correctness_lint() -> None:
    workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")

    assert "python -m compileall -q src scripts tests" in workflow
    assert (
        "ruff check src scripts tests --select "
        "E9,F401,F541,F63,F7,F82,E722,F841,S110,ASYNC221,"
        "PLW1508,PLW1510,RUF012,B017,DTZ001,DTZ005,DTZ007"
    ) in workflow
    assert "python -m src.cli configure --project-root ." in workflow
    assert "docker compose config --quiet" in workflow
