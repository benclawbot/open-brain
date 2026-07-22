from __future__ import annotations

import httpx

from src.providers import (
    MemoryProvider,
    OpenBrainProviderClient,
    ProviderCapability,
    ProviderDescriptor,
    ProviderScope,
    RecallRequest,
    RememberRequest,
)


def _descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id="medusa",
        display_name="Medusa",
        version="1.0.0",
        capabilities={
            ProviderCapability.RECALL,
            ProviderCapability.REMEMBER,
            ProviderCapability.SESSION_LIFECYCLE,
        },
    )


def test_provider_client_conforms_to_protocol() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "healthy"}))
    client = OpenBrainProviderClient(_descriptor(), client=httpx.Client(transport=transport, base_url="http://test"))

    assert isinstance(client, MemoryProvider)


def test_recall_normalizes_scope_and_budgets() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.read() and __import__("json").loads(request.content))
        return httpx.Response(200, json={"items": []})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    client = OpenBrainProviderClient(_descriptor(), client=http_client)

    result = client.recall(
        RecallRequest(
            query="continue the refactor",
            scope=ProviderScope(project_id="00000000-0000-0000-0000-000000000001"),
            token_budget=900,
            max_items=12,
        )
    )

    assert result == {"items": []}
    assert captured["query"] == "continue the refactor"
    assert captured["project_id"] == "00000000-0000-0000-0000-000000000001"
    assert captured["token_budget"] == 900
    assert captured["max_items"] == 12
    assert "task_id" not in captured


def test_remember_sets_provider_identity_and_is_idempotent_by_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(201, json={"id": "event-1", "duplicate": False})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    client = OpenBrainProviderClient(_descriptor(), client=http_client)

    result = client.remember(
        RememberRequest(
            event_type="conversation.user_message",
            idempotency_key="medusa:session-7:message-19",
            payload={"content": "Use the provider SDK."},
        )
    )

    assert result["duplicate"] is False
    assert captured["source_system"] == "medusa"
    assert captured["idempotency_key"] == "medusa:session-7:message-19"
    assert captured["authority"] == "provider_inference"


def test_health_includes_provider_descriptor() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "healthy"}))
    client = OpenBrainProviderClient(
        _descriptor(),
        client=httpx.Client(transport=transport, base_url="http://test"),
    )

    result = client.health()

    assert result["status"] == "healthy"
    assert result["provider"]["provider_id"] == "medusa"
    assert "recall" in result["provider"]["capabilities"]
