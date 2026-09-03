"""Regression tests for oversized and failed embedding recovery."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
import asyncio
import uuid

import pytest
import requests


class _FakeEmbedder:
    def __init__(self, *, max_chars=8, overlap=2, fail_on_call=None):
        self.config = SimpleNamespace(
            max_chars=max_chars,
            chunk_overlap=overlap,
        )
        self.calls = []
        self.fail_on_call = fail_on_call

    def embed(self, text):
        self.calls.append(text)
        if self.fail_on_call == len(self.calls):
            raise requests.ConnectionError("provider down")
        return [3.0, 4.0]


def _cursor(*, row=None):
    cursor = Mock()
    cursor.fetchone.return_value = row

    @contextmanager
    def manager():
        yield cursor

    return cursor, manager


def test_long_embedding_is_chunked_and_pooled():
    from src import embedder

    fake = _FakeEmbedder(max_chars=8, overlap=2)
    with patch.object(embedder, "_embedder", fake):
        result = embedder.create_embedding("abcdefghijklmnopqr")

    assert len(fake.calls) == 3
    assert all(len(chunk) <= 8 for chunk in fake.calls)
    assert fake.calls[0][-2:] == fake.calls[1][:2]
    assert result == pytest.approx([0.6, 0.8])


def test_chunk_provider_failure_propagates_instead_of_silently_degrading():
    from src import embedder

    fake = _FakeEmbedder(max_chars=8, overlap=2, fail_on_call=2)
    with patch.object(embedder, "_embedder", fake):
        with pytest.raises(requests.ConnectionError):
            embedder.create_embedding("abcdefghijklmnopqr")

    assert len(fake.calls) == 2


def test_regeneration_retries_memory_after_provider_failure():
    from src import embedding_regeneration as regeneration

    memory_id = uuid.uuid4()
    with (
        patch.object(
            regeneration,
            "get_memory_embedding_target",
            return_value={"content": "recover me", "has_embedding": False},
        ),
        patch.object(regeneration, "create_embedding", return_value=[0.1, 0.2]) as create,
        patch.object(regeneration, "update_memory_embedding", return_value=True) as update,
    ):
        result = regeneration.regenerate_memory_embedding(memory_id)

    create.assert_called_once_with("recover me")
    update.assert_called_once_with(memory_id, [0.1, 0.2], force=False)
    assert result["status"] == "regenerated"


def test_model_migration_requires_force_before_overwriting_embedding():
    from src import embedding_regeneration as regeneration

    memory_id = uuid.uuid4()
    target = {"content": "migrate me", "has_embedding": True}

    with (
        patch.object(regeneration, "get_memory_embedding_target", return_value=target),
        patch.object(regeneration, "create_embedding") as create,
        patch.object(regeneration, "update_memory_embedding") as update,
    ):
        result = regeneration.regenerate_memory_embedding(memory_id)

    assert result == {
        "id": str(memory_id),
        "status": "unchanged",
        "reason": "embedding_exists",
    }
    create.assert_not_called()
    update.assert_not_called()

    with (
        patch.object(regeneration, "get_memory_embedding_target", return_value=target),
        patch.object(regeneration, "create_embedding", return_value=[0.9, 0.8]) as create,
        patch.object(regeneration, "update_memory_embedding", return_value=True) as update,
    ):
        result = regeneration.regenerate_memory_embedding(memory_id, force=True)

    create.assert_called_once_with("migrate me")
    update.assert_called_once_with(memory_id, [0.9, 0.8], force=True)
    assert result == {
        "id": str(memory_id),
        "status": "regenerated",
        "force": True,
    }


def test_provider_failure_does_not_replace_existing_embedding():
    from src import embedding_regeneration as regeneration

    memory_id = uuid.uuid4()
    with (
        patch.object(
            regeneration,
            "get_memory_embedding_target",
            return_value={"content": "retry later", "has_embedding": False},
        ),
        patch.object(
            regeneration,
            "create_embedding",
            side_effect=requests.ConnectionError("provider down"),
        ),
        patch.object(regeneration, "update_memory_embedding") as update,
    ):
        with pytest.raises(requests.ConnectionError):
            regeneration.regenerate_memory_embedding(memory_id)

    update.assert_not_called()


def test_database_update_is_null_only_unless_forced():
    from src.db import attribution

    memory_id = uuid.uuid4()
    cursor, manager = _cursor(row={"id": memory_id})
    with patch.object(attribution, "get_db_cursor", manager):
        assert attribution.update_memory_embedding(
            memory_id, [0.1, 0.2], force=False
        )

    statement, params = cursor.execute.call_args.args
    assert "embedding IS NULL" in statement
    assert params == ([0.1, 0.2], memory_id, False)


def test_rest_and_mcp_expose_regeneration_controls():
    from src.api.main import EmbeddingRegenerationRequest, app
    from src import main

    assert EmbeddingRegenerationRequest(force=True).force is True
    assert any(
        route.path == "/memories/{memory_id}/regenerate-embedding"
        for route in app.routes
    )

    tools = asyncio.run(main.list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}
    schema = schemas["memory_regenerate_embedding"]
    assert schema["required"] == ["memory_id"]
    assert schema["properties"]["force"]["default"] is False
