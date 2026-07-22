"""Agent-aware memory queries.

This module adds exact authoring-agent attribution without changing the legacy
query API. Existing rows remain valid with ``captured_by = NULL``.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .connection import get_db_cursor


_MEMORY_COLUMNS = """
    id, source, source_id, captured_by, content, raw_content,
    entities, tags, tag_sources, importance, created_at,
    original_date, language, metadata
"""


def _decode_memory(row: Dict[str, Any]) -> Dict[str, Any]:
    memory = dict(row)
    for field in ("entities", "metadata", "tag_sources"):
        if isinstance(memory.get(field), str):
            memory[field] = json.loads(memory[field])
    if "score" in memory:
        memory["score"] = float(memory.get("score", 0.5))
    return memory


def insert_memory(
    source: str,
    content: str,
    embedding: Optional[List[float]] = None,
    source_id: Optional[str] = None,
    captured_by: Optional[str] = None,
    raw_content: Optional[str] = None,
    entities: Optional[Dict] = None,
    tags: Optional[List[str]] = None,
    tag_sources: Optional[Dict] = None,
    importance: float = 0.5,
    original_date: Optional[datetime] = None,
    language: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> uuid.UUID:
    """Insert a memory with optional exact agent/session attribution."""
    memory_id = uuid.uuid4()
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO memory (
                id, source, source_id, captured_by, content, raw_content,
                embedding, entities, tags, tag_sources, importance,
                original_date, language, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                str(memory_id),
                source,
                source_id,
                captured_by,
                content,
                raw_content,
                embedding,
                json.dumps(dict(entities) if entities else {}),
                list(tags) if tags else [],
                json.dumps(dict(tag_sources) if tag_sources else {}),
                importance,
                original_date,
                language,
                json.dumps(dict(metadata) if metadata else {}),
            ),
        )
    return memory_id


def search_memories(
    query: str,
    embedding: Optional[List[float]] = None,
    limit: int = 5,
    sources: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    captured_by: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Search memories with exact agent attribution filtering."""
    conditions: List[str] = []
    params: List[Any] = []

    if sources:
        conditions.append("source = ANY(%s)")
        params.append(sources)
    if tags:
        conditions.append("tags && %s")
        params.append(tags)
    if captured_by:
        conditions.append("captured_by = ANY(%s)")
        params.append(captured_by)
    if date_from:
        conditions.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= %s")
        params.append(date_to)

    filter_where = " AND ".join(conditions) if conditions else "TRUE"

    if embedding:
        embedding_where = (
            f"{filter_where} AND embedding IS NOT NULL"
            if filter_where != "TRUE"
            else "embedding IS NOT NULL"
        )
        statement = f"""
            SELECT {_MEMORY_COLUMNS}, (embedding <=> %s::vector) AS score
            FROM memory
            WHERE {embedding_where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        final_params = [embedding, *params, embedding, limit]
    elif query:
        text_where = (
            f"content ILIKE %s AND {filter_where}"
            if filter_where != "TRUE"
            else "content ILIKE %s"
        )
        statement = f"""
            SELECT {_MEMORY_COLUMNS}, 1.0 AS score
            FROM memory
            WHERE {text_where}
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """
        final_params = [f"%{query}%", *params, limit]
    else:
        statement = f"""
            SELECT {_MEMORY_COLUMNS}, 0.5 AS score
            FROM memory
            WHERE {filter_where}
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """
        final_params = [*params, limit]

    with get_db_cursor() as cursor:
        cursor.execute(statement, final_params)
        return [_decode_memory(row) for row in cursor.fetchall()]


def get_memory_by_id(memory_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Fetch one memory including agent attribution."""
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT {_MEMORY_COLUMNS} FROM memory WHERE id = %s",
            (memory_id,),
        )
        row = cursor.fetchone()
    return _decode_memory(row) if row else None


def get_recent_memories(
    limit: int = 50,
    offset: int = 0,
    source: Optional[str] = None,
    captured_by: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return recent memories filtered by transport and/or authoring agent."""
    conditions: List[str] = []
    params: List[Any] = []
    if source:
        conditions.append("source = %s")
        params.append(source)
    if captured_by:
        conditions.append("captured_by = %s")
        params.append(captured_by)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    statement = f"""
        SELECT {_MEMORY_COLUMNS}
        FROM memory
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    with get_db_cursor() as cursor:
        cursor.execute(statement, [*params, limit, offset])
        return [_decode_memory(row) for row in cursor.fetchall()]
