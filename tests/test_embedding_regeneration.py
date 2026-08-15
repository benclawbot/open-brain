"""Tests for stale-embedding regeneration (MCP tool + REST endpoint + DB layer)."""
import asyncio
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest


def _cursor(rows=None, row=None):
    cursor = Mock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = row

    @contextmanager
    def manager():
        yield cursor

    return cursor, manager


# --- DB layer ---

def test_regenerate_returns_none_for_missing_memory():
    from src.db import attribution

    cursor, manager = _cursor(row=None)
    with patch.object(attribution, "get_db_cursor", manager):
        result = attribution.regenerate_embedding(
            __import__("uuid").uuid4(), [0.1, 0.2], force=False
        )
    assert result is None


def test_regenerate_raises_when_embedding_exists_and_no_force():
    from src.db import attribution

    row = {
        "id": "mem-1", "source": "mcp", "source_id": None,
        "captured_by": None, "content": "hello", "raw_content": None,
        "entities": "{}", "tags": [], "tag_sources": "{}",
        "importance": 0.5, "created_at": None, "original_date": None,
        "language": None, "metadata": "{}", "has_embedding": True,
    }
    cursor, manager = _cursor(row=row)
    with patch.object(attribution, "get_db_cursor", manager):
        with pytest.raises(ValueError, match="force=True"):
            attribution.regenerate_embedding(
                __import__("uuid").uuid4(), [0.1, 0.2], force=False
            )


def test_regenerate_updates_null_embedding():
    from src.db import attribution

    mem_id = __import__("uuid").uuid4()
    row_before = {
        "id": str(mem_id), "source": "mcp", "source_id": None,
        "captured_by": None, "content": "hello", "raw_content": None,
        "entities": "{}", "tags": [], "tag_sources": "{}",
        "importance": 0.5, "created_at": None, "original_date": None,
        "language": None, "metadata": "{}", "has_embedding": False,
    }
    row_after = dict(row_before)
    del row_after["has_embedding"]

    cursor, manager = _cursor()
    cursor.fetchone.side_effect = [row_before, row_after]
    with patch.object(attribution, "get_db_cursor", manager):
        result = attribution.regenerate_embedding(mem_id, [0.1, 0.2])

    assert result is not None
    calls = [c.args[0].strip() for c in cursor.execute.call_args_list]
    assert any("UPDATE memory SET embedding" in c for c in calls)


def test_regenerate_force_overwrites_existing():
    from src.db import attribution

    mem_id = __import__("uuid").uuid4()
    row_before = {
        "id": str(mem_id), "source": "mcp", "source_id": None,
        "captured_by": None, "content": "hello", "raw_content": None,
        "entities": "{}", "tags": [], "tag_sources": "{}",
        "importance": 0.5, "created_at": None, "original_date": None,
        "language": None, "metadata": "{}", "has_embedding": True,
    }
    row_after = dict(row_before)
    del row_after["has_embedding"]

    cursor, manager = _cursor()
    cursor.fetchone.side_effect = [row_before, row_after]
    with patch.object(attribution, "get_db_cursor", manager):
        result = attribution.regenerate_embedding(mem_id, [0.1, 0.2], force=True)

    assert result is not None


# --- MCP tool ---

def test_mcp_tool_schema_registered():
    from src import main

    tools = asyncio.run(main.list_tools())
    names = {t.name for t in tools}
    assert "memory_regenerate_embedding" in names

    schema = next(t for t in tools if t.name == "memory_regenerate_embedding")
    assert "memory_id" in schema.inputSchema["properties"]
    assert "force" in schema.inputSchema["properties"]


def test_mcp_handler_returns_error_for_invalid_id():
    from src import main

    result = asyncio.run(main.handle_memory_regenerate_embedding({"memory_id": "not-a-uuid"}))
    assert "Invalid memory ID" in result[0].text


def test_mcp_handler_returns_error_for_missing_memory():
    from src import main

    cursor, manager = _cursor(row=None)
    with patch("src.main.get_memory_by_id", return_value=None):
        result = asyncio.run(main.handle_memory_regenerate_embedding({
            "memory_id": "00000000-0000-0000-0000-000000000001",
        }))
    assert "not found" in result[0].text


def test_mcp_handler_regenerates_successfully():
    from src import main

    memory = {"id": "00000000-0000-0000-0000-000000000001", "content": "hello"}
    with patch("src.main.get_memory_by_id", return_value=memory), \
         patch("src.main.create_embedding", return_value=[0.1, 0.2]), \
         patch("src.main.regenerate_embedding") as mock_regen:
        result = asyncio.run(main.handle_memory_regenerate_embedding({
            "memory_id": "00000000-0000-0000-0000-000000000001",
        }))
    assert "regenerated" in result[0].text
    mock_regen.assert_called_once()
