from __future__ import annotations

import json
from pathlib import Path

import httpx

from src.openbrain_medusa_adapter import MedusaMemoryAdapter, MedusaSessionContext
from src.providers import OpenBrainProviderClient, ProviderScope


def _context(tmp_path: Path) -> MedusaSessionContext:
    return MedusaSessionContext(
        session_key="session-42",
        workspace_path=tmp_path,
        scope=ProviderScope(project_id="00000000-0000-0000-0000-000000000001"),
        agent_version="0.9.0",
    )


def test_recall_formats_trust_labeled_prompt_block(tmp_path: Path) -> None:
    packet = {
        "packet_id": "00000000-0000-0000-0000-000000000010",
        "items": [
            {"kind": "decision", "trust": "user_confirmed", "text": "Use Open Brain."},
            {"kind": "warning", "trust": "stale", "text": "Old adapter path."},
        ],
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=packet))
    provider = OpenBrainProviderClient(
        MedusaMemoryAdapter.descriptor,
        client=httpx.Client(transport=transport, base_url="http://test"),
    )
    adapter = MedusaMemoryAdapter(_context(tmp_path), client=provider)

    result = adapter.recall(token_budget=900, max_items=10)

    assert result.unavailable is False
    assert result.item_count == 2
    assert "[decision; trust=user_confirmed] Use Open Brain." in result.prompt_block
    assert "[warning; trust=stale] Old adapter path." in result.prompt_block


def test_user_message_sets_authority_and_deterministic_identity(tmp_path: Path) -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "event-1", "duplicate": False})

    provider = OpenBrainProviderClient(
        MedusaMemoryAdapter.descriptor,
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"),
    )
    adapter = MedusaMemoryAdapter(_context(tmp_path), client=provider)

    adapter.user_message(7, "Continue the roadmap.")
    adapter.user_message(7, "Continue the roadmap.")

    assert captured[0]["idempotency_key"] == captured[1]["idempotency_key"]
    assert captured[0]["source_system"] == "medusa"
    assert captured[0]["authority"] == "user_confirmed"
    assert captured[0]["payload"]["agent_version"] == "0.9.0"


def test_failed_write_is_spooled_and_replayed(tmp_path: Path) -> None:
    failing = httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "offline"}))
    provider = OpenBrainProviderClient(
        MedusaMemoryAdapter.descriptor,
        client=httpx.Client(transport=failing, base_url="http://test"),
    )
    context = _context(tmp_path)
    adapter = MedusaMemoryAdapter(context, client=provider)

    result = adapter.session_started({"mode": "yolo"})

    assert result["status"] == "spooled"
    spool = context.effective_spool_path()
    assert spool.exists()
    assert "spooled_at" in json.loads(spool.read_text())

    succeeding = httpx.MockTransport(
        lambda request: httpx.Response(201, json={"id": "event-2", "duplicate": False})
    )
    adapter.client = OpenBrainProviderClient(
        MedusaMemoryAdapter.descriptor,
        client=httpx.Client(transport=succeeding, base_url="http://test"),
    )

    replay = adapter.replay_spool()

    assert replay == {"replayed": 1, "remaining": 0}
    assert not spool.exists()


def test_recall_failure_is_soft(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "offline"}))
    provider = OpenBrainProviderClient(
        MedusaMemoryAdapter.descriptor,
        client=httpx.Client(transport=transport, base_url="http://test"),
    )
    adapter = MedusaMemoryAdapter(_context(tmp_path), client=provider)

    result = adapter.recall()

    assert result.unavailable is True
    assert result.prompt_block == ""
