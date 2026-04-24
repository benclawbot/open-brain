"""
SQL queries for Open Brain memory operations.
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from .connection import get_db_cursor


def insert_memory(
    source: str,
    content: str,
    embedding: Optional[List[float]] = None,
    source_id: Optional[str] = None,
    raw_content: Optional[str] = None,
    entities: Optional[Dict] = None,
    tags: Optional[List[str]] = None,
    tag_sources: Optional[Dict] = None,
    importance: float = 0.5,
    original_date: Optional[datetime] = None,
    language: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> uuid.UUID:
    """
    Insert a new memory into the database.
    
    Args:
        source: Source of the memory (e.g., 'chat', 'note', 'email')
        content: The main content of the memory
        embedding: Vector embedding for semantic search
        source_id: Optional source-specific ID
        raw_content: Raw/original content before processing
        entities: Extracted entities as JSON
        tags: List of tags
        tag_sources: Source of each tag
        importance: Importance score (0.0 to 1.0)
        original_date: Original date of the memory
        language: Language code
        metadata: Additional metadata
    
    Returns:
        UUID of the inserted memory
    """
    memory_id = uuid.uuid4()
    
    # Ensure JSON fields are proper Python dicts/lists
    entities_dict = dict(entities) if entities else {}
    tags_list = list(tags) if tags else []
    tag_sources_dict = dict(tag_sources) if tag_sources else {}
    metadata_dict = dict(metadata) if metadata else {}
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO memory (
                id, source, source_id, content, raw_content, embedding,
                entities, tags, tag_sources, importance, original_date,
                language, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            str(memory_id),
            source,
            source_id,
            content,
            raw_content,
            embedding,
            json.dumps(entities_dict),
            tags_list,
            json.dumps(tag_sources_dict),
            importance,
            original_date,
            language,
            json.dumps(metadata_dict)
        ))
    
    return memory_id


def search_memories(
    query: str,
    embedding: Optional[List[float]] = None,
    limit: int = 5,
    sources: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Search memories by text, embedding, or filters.
    
    Args:
        query: Text search query
        embedding: Vector embedding for semantic search
        limit: Maximum number of results
        sources: Filter by sources
        tags: Filter by tags
        date_from: Filter from date
        date_to: Filter to date
    
    Returns:
        List of memory records with scores
    """
    # Build filter conditions (source, tags, dates — NOT text, which is
    # handled differently depending on whether we have an embedding)
    filter_conditions = []
    filter_params = []

    if sources:
        filter_conditions.append("source = ANY(%s)")
        filter_params.append(sources)

    if tags:
        filter_conditions.append("tags && %s")
        filter_params.append(tags)

    if date_from:
        filter_conditions.append("created_at >= %s")
        filter_params.append(date_from)

    if date_to:
        filter_conditions.append("created_at <= %s")
        filter_params.append(date_to)

    filter_where = " AND ".join(filter_conditions) if filter_conditions else "TRUE"

    if embedding:
        # Semantic search: use vector distance for ranking, skip text ILIKE
        # (the whole point is to find semantically similar content, not literal matches)
        emb_where = f"{filter_where} AND embedding IS NOT NULL" if filter_where != "TRUE" else "embedding IS NOT NULL"
        query_sql = f"""
            SELECT
                id, source, source_id, content, raw_content,
                entities, tags, tag_sources, importance, created_at,
                original_date, language, metadata,
                (embedding <=> %s::vector) as score
            FROM memory
            WHERE {emb_where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params_final = [embedding] + filter_params + [embedding, limit]
    else:
        # Text fallback: use ILIKE for filtering and scoring
        if query:
            text_where = f"content ILIKE %s AND {filter_where}" if filter_where != "TRUE" else "content ILIKE %s"
            query_sql = f"""
                SELECT
                    id, source, source_id, content, raw_content,
                    entities, tags, tag_sources, importance, created_at,
                    original_date, language, metadata,
                    1.0 as score
                FROM memory
                WHERE {text_where}
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """
            params_final = [f"%{query}%"] + filter_params + [limit]
        else:
            # No query and no embedding — just return by filters
            query_sql = f"""
                SELECT
                    id, source, source_id, content, raw_content,
                    entities, tags, tag_sources, importance, created_at,
                    original_date, language, metadata,
                    0.5 as score
                FROM memory
                WHERE {filter_where}
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """
            params_final = filter_params + [limit]
    
    with get_db_cursor() as cursor:
        cursor.execute(query_sql, params_final)
        results = cursor.fetchall()
    
    # Convert results to dict with proper JSON parsing
    memories = []
    for row in results:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        if isinstance(mem.get('metadata'), str):
            mem['metadata'] = json.loads(mem['metadata'])
        if isinstance(mem.get('tag_sources'), str):
            mem['tag_sources'] = json.loads(mem['tag_sources'])
        mem['score'] = float(row.get('score', 0.5))
        memories.append(mem)
    
    return memories


def get_memory_by_id(memory_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get a single memory by ID."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, source, source_id, content, raw_content,
                   entities, tags, tag_sources, importance, created_at,
                   original_date, language, metadata
            FROM memory
            WHERE id = %s
        """, (memory_id,))
        row = cursor.fetchone()
    
    if row:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        if isinstance(mem.get('metadata'), str):
            mem['metadata'] = json.loads(mem['metadata'])
        if isinstance(mem.get('tag_sources'), str):
            mem['tag_sources'] = json.loads(mem['tag_sources'])
        return mem
    return None


def get_related_memories(
    memory_id: uuid.UUID,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get memories related to a given memory."""
    memory = get_memory_by_id(memory_id)
    if not memory or not memory.get('embedding'):
        return []
    
    # Use vector similarity
    return search_memories(
        query="",
        embedding=memory['embedding'],
        limit=limit
    )


def get_memories_by_entity(
    entity_type: str,
    entity_name: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get memories containing a specific entity."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, source, source_id, content, raw_content,
                   entities, tags, tag_sources, importance, created_at,
                   original_date, language, metadata
            FROM memory
            WHERE entities->%s ? %s
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """, (entity_type, entity_name, limit))
        results = cursor.fetchall()
    
    memories = []
    for row in results:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        if isinstance(mem.get('metadata'), str):
            mem['metadata'] = json.loads(mem['metadata'])
        if isinstance(mem.get('tag_sources'), str):
            mem['tag_sources'] = json.loads(mem['tag_sources'])
        memories.append(mem)

    return memories


def get_today_memories(limit: int = 10) -> List[Dict[str, Any]]:
    """Get memories from today."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, source, source_id, content, raw_content,
                   entities, tags, tag_sources, importance, created_at,
                   original_date, language, metadata
            FROM memory
            WHERE created_at >= CURRENT_DATE
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
    
    memories = []
    for row in results:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        if isinstance(mem.get('metadata'), str):
            mem['metadata'] = json.loads(mem['metadata'])
        memories.append(mem)
    
    return memories


def get_memory_stats() -> Dict[str, Any]:
    """Get memory statistics."""
    with get_db_cursor() as cursor:
        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM memory")
        total = cursor.fetchone()['total']
        
        # By source
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM memory 
            GROUP BY source 
            ORDER BY count DESC
        """)
        by_source = {row['source']: row['count'] for row in cursor.fetchall()}
        
        # Top tags
        cursor.execute("""
            SELECT tag, COUNT(*) as count
            FROM memory, UNNEST(tags) as tag
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 20
        """)
        top_tags = {row['tag']: row['count'] for row in cursor.fetchall()}
        
        # This week
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM memory 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """)
        this_week = cursor.fetchone()['count']
        
        # This month
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM memory 
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        """)
        this_month = cursor.fetchone()['count']
    
    return {
        'total': total,
        'by_source': by_source,
        'top_tags': top_tags,
        'this_week': this_week,
        'this_month': this_month
    }


def get_trending_tags(weeks: int = 4, limit: int = 10) -> Dict[str, int]:
    """Get trending tags over the specified number of weeks."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT tag, COUNT(*) as count
            FROM memory, UNNEST(tags) as tag
            WHERE created_at >= CURRENT_DATE - (%s * INTERVAL '1 week')
            GROUP BY tag
            ORDER BY count DESC
            LIMIT %s
        """, (weeks, limit))
        results = cursor.fetchall()
    
    return {row['tag']: row['count'] for row in results}


def get_recent_memories(
    limit: int = 50,
    offset: int = 0,
    source: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get recent memories with pagination.
    
    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        source: Optional source filter
    
    Returns:
        List of memory records
    """
    with get_db_cursor() as cursor:
        if source:
            cursor.execute("""
                SELECT id, source, source_id, content, raw_content,
                       entities, tags, tag_sources, importance, created_at,
                       original_date, language, metadata
                FROM memory
                WHERE source = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (source, limit, offset))
        else:
            cursor.execute("""
                SELECT id, source, source_id, content, raw_content,
                       entities, tags, tag_sources, importance, created_at,
                       original_date, language, metadata
                FROM memory
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
        
        results = cursor.fetchall()
    
    memories = []
    for row in results:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        if isinstance(mem.get('metadata'), str):
            mem['metadata'] = json.loads(mem['metadata'])
        if isinstance(mem.get('tag_sources'), str):
            mem['tag_sources'] = json.loads(mem['tag_sources'])
        memories.append(mem)
    
    return memories


def get_memories_for_report(
    days: int = 7
) -> List[Dict[str, Any]]:
    """Get all memories from the last N days for report generation."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, source, content, tags, entities, created_at
            FROM memory
            WHERE created_at >= CURRENT_DATE - (%s * INTERVAL '1 day')
            ORDER BY created_at DESC
        """, (days,))
        results = cursor.fetchall()
    
    memories = []
    for row in results:
        mem = dict(row)
        if isinstance(mem.get('entities'), str):
            mem['entities'] = json.loads(mem['entities'])
        memories.append(mem)
    
    return memories
