from pathlib import Path

import httpx
import pytest

from src.providers.client import OpenBrainProviderClient
from src.providers.contracts import ProviderDescriptor, RememberRequest
from src.providers.host_config import HostAdapterConfig, install_env_file, uninstall_env_file


def descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(provider_id="codex", display_name="Codex", version="1.0.0", capabilities=set())


def test_host_config_reads_environment(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_URL", "https://brain.example.test/")
    monkeypatch.setenv("OPENBRAIN_API_KEY", "secret")
    monkeypatch.setenv("OPENBRAIN_TIMEOUT", "7.5")

    config = HostAdapterConfig.from_env()

    assert config.base_url == "https://brain.example.test"
    assert config.api_key == "secret"
    assert config.timeout == 7.5


def test_host_config_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_TIMEOUT", "0")
    with pytest.raises(ValueError):
        HostAdapterConfig.from_env()


def test_install_and_uninstall_env_file(tmp_path: Path):
    path = tmp_path / "codex.env"
    installed = install_env_file(path, HostAdapterConfig(api_key="secret"))

    assert installed == path
    assert "OPENBRAIN_API_KEY=secret" in path.read_text()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert uninstall_env_file(path) is True
    assert uninstall_env_file(path) is False


def test_provider_client_authenticates_and_attributes(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_API_KEY", "secret")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["captured_by_header"] = request.headers.get("x-openbrain-captured-by")
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"status": "stored"})

    transport = httpx.MockTransport(handler)
    raw_client = httpx.Client(transport=transport, base_url="http://test")
    client = OpenBrainProviderClient(descriptor(), client=raw_client)
    client.remember(RememberRequest(event_type="session.started", idempotency_key="codex:test", payload={}))

    assert captured["authorization"] == "Bearer secret"
    assert captured["captured_by_header"] == "codex"
    assert captured["json"]["captured_by"] == "codex"
