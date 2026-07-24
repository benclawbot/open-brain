"""Shared, private runtime configuration for the server and its clients."""

from __future__ import annotations

import csv
import os
import secrets
import shutil
import subprocess
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

_RUNTIME_KEYS = (
    "OPENBRAIN_URL",
    "OPENBRAIN_API_KEY",
    "OPENBRAIN_AUTH_REQUIRED",
    "OPENBRAIN_TIMEOUT",
)
_PLACEHOLDERS = {
    "",
    "change-me",
    "openbrain",
    "replace-me",
    "replace-with-generated-secret",
    "your_secure_database_password",
    "your_openbrain_api_key",
}


def runtime_config_dir() -> Path:
    configured = os.getenv("OPENBRAIN_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "openbrain"


def runtime_env_path() -> Path:
    return runtime_config_dir() / ".env"


def restrict_file_permissions(path: Path) -> None:
    """Restrict a secret-bearing file to the current user on each platform."""
    if os.name != "nt":
        path.chmod(0o600)
        return

    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    user_sid = next(csv.reader([identity]))[1]
    subprocess.run(
        [
            "icacls",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{user_sid}:(F)",
            "/grant:r",
            "*S-1-5-18:(F)",
            "/grant:r",
            "*S-1-5-32-544:(F)",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _usable_secret(value: str | None) -> bool:
    return bool(value and len(value) >= 32 and value.lower() not in _PLACEHOLDERS)


def _read_key(path: Path) -> str | None:
    if not path.is_file():
        return None
    value = dotenv_values(path).get("OPENBRAIN_API_KEY")
    return str(value) if value else None


def _ensure_env_file(
    path: Path,
    api_key: str,
    *,
    include_database: bool = False,
) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Open Brain private runtime configuration\n", encoding="utf-8")

    current = dotenv_values(path)
    defaults = {
        "OPENBRAIN_URL": "http://127.0.0.1:8000",
        "OPENBRAIN_API_KEY": api_key,
        "OPENBRAIN_AUTH_REQUIRED": "true",
        "OPENBRAIN_TIMEOUT": "3",
    }
    for name, value in defaults.items():
        existing = current.get(name)
        if name == "OPENBRAIN_API_KEY" or not existing:
            set_key(str(path), name, value, quote_mode="never")
    if include_database:
        database_password = current.get("DB_PASSWORD")
        if not database_password or str(database_password).lower() in _PLACEHOLDERS:
            set_key(
                str(path),
                "DB_PASSWORD",
                secrets.token_urlsafe(24),
                quote_mode="never",
            )
    restrict_file_permissions(path)
    return path


def configure_runtime_environment(project_root: Path | None = None) -> Path:
    """Generate credentials once and share them with local server and clients."""
    user_path = runtime_env_path()
    project_path = (
        project_root.expanduser().resolve() / ".env" if project_root is not None else None
    )
    if project_path and not project_path.exists():
        example = project_path.parent / ".env.example"
        if example.is_file():
            project_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(example, project_path)
    candidates = (
        os.getenv("OPENBRAIN_API_KEY"),
        _read_key(project_path) if project_path else None,
        _read_key(user_path),
    )
    api_key = next((value for value in candidates if _usable_secret(value)), None)
    if api_key is None:
        api_key = secrets.token_urlsafe(32)

    _ensure_env_file(user_path, api_key)
    target = (
        _ensure_env_file(project_path, api_key, include_database=True)
        if project_path
        else user_path
    )
    os.environ["OPENBRAIN_API_KEY"] = api_key
    os.environ.setdefault("OPENBRAIN_URL", "http://127.0.0.1:8000")
    os.environ.setdefault("OPENBRAIN_AUTH_REQUIRED", "true")
    os.environ.setdefault("OPENBRAIN_TIMEOUT", "3")
    return target


def load_runtime_environment() -> None:
    """Load project-local settings first, then the per-user installation settings."""
    candidates: list[Path] = []
    explicit = os.getenv("OPENBRAIN_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(Path.cwd() / ".env")
    source_root = Path(__file__).resolve().parents[1]
    candidates.append(source_root / ".env")
    candidates.append(runtime_env_path())

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        load_dotenv(resolved, override=False)


def runtime_settings_from_file(path: Path | None = None) -> dict[str, str]:
    """Return only Open Brain runtime values without exposing unrelated secrets."""
    values = dotenv_values(path or runtime_env_path())
    return {
        key: str(values[key])
        for key in _RUNTIME_KEYS
        if values.get(key) is not None
    }
