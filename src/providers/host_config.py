"""Environment-driven configuration for coding-agent host adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HostAdapterConfig:
    """Resolved Open Brain connection settings for an agent host."""

    base_url: str = "http://127.0.0.1:8000"
    api_key: str | None = None
    timeout: float = 3.0

    @classmethod
    def from_env(cls) -> "HostAdapterConfig":
        base_url = os.getenv("OPENBRAIN_URL", "http://127.0.0.1:8000").strip().rstrip("/")
        api_key = os.getenv("OPENBRAIN_API_KEY") or None
        try:
            timeout = float(os.getenv("OPENBRAIN_TIMEOUT", "3"))
        except ValueError as exc:
            raise ValueError("OPENBRAIN_TIMEOUT must be a number") from exc
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("OPENBRAIN_URL must use http:// or https://")
        if timeout <= 0 or timeout > 120:
            raise ValueError("OPENBRAIN_TIMEOUT must be greater than 0 and at most 120 seconds")
        return cls(base_url=base_url, api_key=api_key, timeout=timeout)

    def headers(self, provider_id: str, version: str) -> dict[str, str]:
        headers = {
            "User-Agent": f"openbrain-provider/{provider_id}/{version}",
            "X-OpenBrain-Provider": provider_id,
            "X-OpenBrain-Captured-By": provider_id,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def render_env_file(config: HostAdapterConfig) -> str:
    """Render a shell-compatible environment file without inventing secrets."""
    lines = [
        f"OPENBRAIN_URL={config.base_url}",
        f"OPENBRAIN_TIMEOUT={config.timeout:g}",
    ]
    if config.api_key:
        lines.append(f"OPENBRAIN_API_KEY={config.api_key}")
    return "\n".join(lines) + "\n"


def install_env_file(path: Path, config: HostAdapterConfig, *, overwrite: bool = False) -> Path:
    """Install host settings atomically with private file permissions."""
    path = path.expanduser()
    if path.exists() and not overwrite:
        raise FileExistsError(f"Configuration already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(render_env_file(config), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    return path


def uninstall_env_file(path: Path) -> bool:
    path = path.expanduser()
    if not path.exists():
        return False
    path.unlink()
    return True
