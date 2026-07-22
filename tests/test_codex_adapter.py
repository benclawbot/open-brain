from __future__ import annotations

from pathlib import Path
from typing import Any

from src.openbrain_codex_adapter import CodexSessionAdapter, CodexSessionContext
from src.providers import (
    ProviderScope,
    RecallRequest,
    RememberRequest,
    run_provider_conformance,
)


class FakeClient:
    def __init__(self) -> None:
        self.remembered: list[RememberRequest] = []
        self.recalled: list[RecallRequest] = []

    def health(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        self.recalled.append(request)
        return {"items": [], "scope": request.scope.model_dump(mode="json")}

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        duplicate = any(
            item.idempotency_key == request.idempotency_key for item in self.remembered
        )
        self.remembered.append(request)
        return {"status": "stored", "duplicate": duplicate}

    def close(self) -> None:
        return None


def _adapter() -> tuple[CodexSessionAdapter, FakeClient]:
    client = FakeClient()
    context = CodexSessionContext(
        session_key="codex-session-42",
        workspace_path=Path("/workspace/open-brain"),
        client_version="1.2.3",
        scope=ProviderScope(
            project_id="00000000-0000-0000-0000-000000000042"
        ),
    )
    return CodexSessionAdapter(context, client=client), client


def test_codex_adapter_passes_shared_conformance_gate() -> None:
    adapter, _ = _adapter()

    report = run_provider_conformance(adapter)

    report.require_success()
    assert report.provider_id == "codex"
    assert "remember_duplicate" in report.passed


def test_recall_forces_host_session_scope() -> None:
    adapter, client = _adapter()

    adapter.recall(RecallRequest(token_budget=800, max_items=10))

    assert client.recalled[0].scope.project_id is not None
    assert client.recalled[0].token_budget == 800


def test_lifecycle_callbacks_use_deterministic_event_identity() -> None:
    adapter, client = _adapter()

    first = adapter.user_message(7, "Continue the provider work")
    second = adapter.user_message(7, "Continue the provider work")

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert client.remembered[0].idempotency_key.startswith("codex:")
    assert client.remembered[0].authority.value == "user_confirmed"
    assert client.remembered[0].payload["client_version"] == "1.2.3"


def test_tool_results_are_tool_observed() -> None:
    adapter, client = _adapter()

    adapter.tool_result(8, "shell", {"exit_code": 0}, success=True)

    event = client.remembered[0]
    assert event.event_type == "tool.result"
    assert event.authority.value == "tool_observed"
    assert event.payload["success"] is True
