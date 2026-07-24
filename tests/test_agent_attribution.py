"""Tests for exact multi-agent memory attribution."""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import Mock, patch

def _cursor(rows=None, row=None):
    cursor = Mock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = row

    @contextmanager
    def manager():
        yield cursor

    return cursor, manager


def test_insert_memory_persists_captured_by():
    from src.db import attribution

    cursor, manager = _cursor()
    with patch.object(attribution, "get_db_cursor", manager):
        attribution.insert_memory(
            source="mcp",
            captured_by="claude-code:session-42",
            content="Remember this",
        )

    statement, params = cursor.execute.call_args.args
    assert "captured_by" in statement
    assert params[3] == "claude-code:session-42"


def test_insert_memory_allows_legacy_null_attribution():
    from src.db import attribution

    cursor, manager = _cursor()
    with patch.object(attribution, "get_db_cursor", manager):
        attribution.insert_memory(source="api", content="Legacy-compatible")

    _, params = cursor.execute.call_args.args
    assert params[3] is None


def test_semantic_search_filters_by_exact_agent():
    from src.db import attribution

    cursor, manager = _cursor()
    with patch.object(attribution, "get_db_cursor", manager):
        attribution.search_memories(
            query="work summary",
            embedding=[0.1, 0.2],
            captured_by=["medusa:session-a"],
            limit=7,
        )

    statement, params = cursor.execute.call_args.args
    assert "captured_by = ANY(%s)" in statement
    assert params == [[0.1, 0.2], ["medusa:session-a"], [0.1, 0.2], 7]


def test_text_search_combines_transport_and_agent_filters():
    from src.db import attribution

    cursor, manager = _cursor()
    with patch.object(attribution, "get_db_cursor", manager):
        attribution.search_memories(
            query="deployment",
            sources=["mcp"],
            captured_by=["codex:repo-open-brain"],
        )

    statement, params = cursor.execute.call_args.args
    assert "source = ANY(%s)" in statement
    assert "captured_by = ANY(%s)" in statement
    assert params == [
        "%deployment%",
        ["mcp"],
        ["codex:repo-open-brain"],
        5,
    ]


def test_recent_memories_filter_by_agent_and_decode_rows():
    from src.db import attribution

    now = datetime.now(timezone.utc)
    cursor, manager = _cursor(rows=[{
        "id": "memory-1",
        "source": "mcp",
        "source_id": None,
        "captured_by": "claude-code:session-1",
        "content": "Status",
        "raw_content": None,
        "entities": "{}",
        "tags": [],
        "tag_sources": "{}",
        "importance": 0.5,
        "created_at": now,
        "original_date": None,
        "language": None,
        "metadata": "{}",
    }])
    with patch.object(attribution, "get_db_cursor", manager):
        results = attribution.get_recent_memories(
            captured_by="claude-code:session-1"
        )

    statement, params = cursor.execute.call_args.args
    assert "captured_by = %s" in statement
    assert params == ["claude-code:session-1", 50, 0]
    assert results[0]["captured_by"] == "claude-code:session-1"
    assert results[0]["metadata"] == {}


def test_rest_models_expose_agent_attribution():
    from src.api.main import MemoryCreate, MemoryResponse, SearchRequest

    assert "captured_by" in MemoryCreate.model_fields
    assert "captured_by" in MemoryResponse.model_fields
    assert "captured_by" in SearchRequest.model_fields


def test_mcp_tool_schemas_expose_agent_attribution():
    import asyncio
    from src import main

    tools = asyncio.run(main.list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}
    assert "captured_by" in schemas["memory_store"]["properties"]
    assert "captured_by" in schemas["memory_search"]["properties"]


def test_mcp_format_includes_attribution_when_present():
    from src.main import format_memory_list

    formatted = format_memory_list([{
        "id": "memory-1",
        "source": "mcp",
        "captured_by": "medusa:session-9",
        "content": "Completed task",
        "tags": [],
        "created_at": datetime.now(timezone.utc),
    }])
    assert "Captured by: medusa:session-9" in formatted
