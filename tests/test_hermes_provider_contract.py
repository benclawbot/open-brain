from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_provider_module():
    agent_module = types.ModuleType("agent")
    memory_provider_module = types.ModuleType("agent.memory_provider")

    class MemoryProvider:
        pass

    memory_provider_module.MemoryProvider = MemoryProvider
    sys.modules["agent"] = agent_module
    sys.modules["agent.memory_provider"] = memory_provider_module

    path = Path(__file__).resolve().parents[1] / "src" / "openbrain_hermes_plugin" / "__init__.py"
    spec = importlib.util.spec_from_file_location("openbrain_provider_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_digest_is_deterministic():
    module = _load_provider_module()
    assert module._digest("a", "b") == module._digest("a", "b")
    assert module._digest("a", "b") != module._digest("b", "a")


def test_client_loads_generated_key_and_authenticates(tmp_path, monkeypatch):
    module = _load_provider_module()
    config_dir = tmp_path / ".config" / "openbrain"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(
        "OPENBRAIN_URL=http://127.0.0.1:8000\n"
        "OPENBRAIN_API_KEY=generated-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENBRAIN_CONFIG_DIR", str(config_dir))
    monkeypatch.delenv("OPENBRAIN_API_KEY", raising=False)

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"ok": True}).encode()

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    settings = module._load_openbrain_environment()
    module._Client(settings["OPENBRAIN_URL"], api_key=settings["OPENBRAIN_API_KEY"]).request(
        "GET",
        "/health",
    )

    assert captured["authorization"] == "Bearer generated-secret"


def test_open_session_preserves_internal_session_id():
    module = _load_provider_module()
    provider = module.OpenBrainMemoryProvider()

    class Client:
        def request(self, method, path, payload=None):
            assert path == "/v1/sessions/open"
            return {"id": "11111111-1111-1111-1111-111111111111"}

    provider._client = Client()
    provider._open_session("external-session", "", "new")
    assert provider._session_record_id == "11111111-1111-1111-1111-111111111111"


def test_enqueued_event_includes_canonical_session_scope(monkeypatch):
    module = _load_provider_module()
    provider = module.OpenBrainMemoryProvider()
    provider._session_record_id = "11111111-1111-1111-1111-111111111111"
    captured = {}

    monkeypatch.setattr(
        provider,
        "_dispatch_or_spool",
        lambda path, payload: captured.update({"path": path, "payload": payload}),
    )
    provider._enqueue_event(
        "conversation.turn_completed",
        {"idempotency_key": "event-key-123", "content": "hello"},
    )

    assert captured["path"] == "/v1/events"
    assert captured["payload"]["scope"]["session_id"] == provider._session_record_id
    assert captured["payload"]["payload"] == {"content": "hello"}
