from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from src.openbrain_claude_adapter import ClaudeSessionAdapter, ClaudeSessionContext
from src.providers import ProviderScope, RecallRequest, RememberRequest, run_provider_conformance


USER_ID = UUID("11111111-1111-4111-8111-111111111111")
PROJECT_ID = UUID("22222222-2222-4222-8222-222222222222")
OTHER_PROJECT_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeClient:
    def __init__(self) -> None:
        self.events: list[RememberRequest] = []
        self.recalls: list[RecallRequest] = []

    def health(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        self.recalls.append(request)
        return {"items": []}

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        duplicate = any(item.idempotency_key == request.idempotency_key for item in self.events)
        self.events.append(request)
        return {"status": "stored", "duplicate": duplicate}

    def close(self) -> None:
        return None


def make_adapter() -> tuple[ClaudeSessionAdapter, FakeClient]:
    client = FakeClient()
    context = ClaudeSessionContext(
        session_key="claude-session-1",
        workspace_path=Path("/workspace/project"),
        client_version="2.0.0",
        scope=ProviderScope(user_identity_id=USER_ID, project_id=PROJECT_ID),
    )
    return ClaudeSessionAdapter(context, client=client), client


def test_claude_adapter_passes_provider_conformance() -> None:
    adapter, _ = make_adapter()
    report = run_provider_conformance(adapter)
    report.require_success()
    assert report.ok


def test_adapter_enforces_context_scope() -> None:
    adapter, client = make_adapter()
    adapter.recall(RecallRequest(scope=ProviderScope(project_id=OTHER_PROJECT_ID)))
    assert client.recalls[-1].scope.project_id == PROJECT_ID


def test_lifecycle_identity_is_deterministic_and_authority_is_preserved() -> None:
    adapter, client = make_adapter()
    first = adapter.user_message(1, "hello")
    second = adapter.user_message(1, "hello")

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert client.events[-1].authority == "user_confirmed"
    assert client.events[-1].event_type == "conversation.user_message"
