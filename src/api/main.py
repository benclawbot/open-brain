"""
Open Brain REST API.
FastAPI server for memory and continuity operations.
"""
import os
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add src to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.continuity import router as continuity_router
from db.connection import init_db
from db.attribution import (
    search_memories,
    get_memory_by_id,
    insert_memory,
    get_recent_memories,
)
from db.queries import get_memory_stats, get_today_memories
from embedder import create_embedding
from extractors.entities import extract_entities
from extractors.tagger import get_tagger
from analytics.trends import TrendAnalyzer
from analytics.weekly_report import generate_weekly_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
    yield


app = FastAPI(
    title="Open Brain API",
    description="REST API for memory management and durable agent continuity",
    version="1.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(continuity_router)


class MemoryCreate(BaseModel):
    content: str
    source: str = "api"
    captured_by: Optional[str] = None
    tags: List[str] = []
    importance: float = 0.5
    metadata: dict = Field(default_factory=dict)


class MemoryResponse(BaseModel):
    id: str
    source: str
    captured_by: Optional[str] = None
    content: str
    tags: List[str]
    entities: dict
    importance: float
    created_at: datetime


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    sources: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    captured_by: Optional[List[str]] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Open Brain API",
        "version": "1.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/memories", response_model=List[MemoryResponse])
async def get_memories(
    limit: int = Query(50, le=100),
    offset: int = 0,
    source: Optional[str] = None,
    captured_by: Optional[str] = None,
):
    """Get memories with optional transport and authoring-agent filters."""
    memories = get_recent_memories(limit, offset, source, captured_by)
    return memories


@app.post("/memories", response_model=dict)
async def create_memory(memory: MemoryCreate):
    """Create a new memory."""
    content = memory.content
    source = memory.source
    captured_by = memory.captured_by
    user_tags = memory.tags
    importance = memory.importance
    metadata = memory.metadata

    entities = extract_entities(content)

    tagger = get_tagger()
    tag_sources = tagger.tag(content, entities, source, user_tags)
    tags = list(tag_sources.keys())

    embedding = None
    try:
        embedding = create_embedding(content)
    except Exception as e:
        print(f"Warning: Could not create embedding: {e}")

    memory_id = insert_memory(
        source=source,
        captured_by=captured_by,
        content=content,
        embedding=embedding,
        entities=entities,
        tags=tags,
        tag_sources=tag_sources,
        importance=importance,
        metadata=metadata
    )

    return {
        "id": str(memory_id),
        "status": "stored",
        "tags": tags,
        "captured_by": captured_by,
    }


@app.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str):
    """Get a specific memory by ID."""
    import uuid
    try:
        parsed_id = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {memory_id}")
    memory = get_memory_by_id(parsed_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return memory


@app.post("/memories/search", response_model=List[MemoryResponse])
async def search_memories_endpoint(search: SearchRequest):
    """Search memories by semantic content and structured filters."""
    query = search.query
    limit = search.limit
    sources = search.sources
    tags = search.tags
    captured_by = search.captured_by

    embedding = None
    if query:
        try:
            embedding = create_embedding(query)
        except Exception as e:
            print(f"Warning: Could not create embedding: {e}")

    results = search_memories(
        query=query,
        embedding=embedding,
        limit=limit,
        sources=sources,
        tags=tags,
        captured_by=captured_by,
    )

    for result in results:
        if hasattr(result.get("created_at", ""), "isoformat"):
            result["created_at"] = result["created_at"].isoformat()
        elif "created_at" in result and not isinstance(result["created_at"], str):
            result["created_at"] = str(result["created_at"])

    return results


@app.get("/stats")
async def get_stats():
    """Get memory statistics."""
    stats = get_memory_stats()
    return stats


@app.get("/trends")
async def get_trends(weeks: int = Query(4, le=12)):
    """Get trending topics."""
    analyzer = TrendAnalyzer()
    trends = analyzer.get_top_trending(weeks)
    return {"trends": trends}


@app.get("/report/weekly")
async def get_weekly_report(days: int = Query(7, le=30)):
    """Generate weekly report."""
    report = generate_weekly_report(days)
    return {"report": report}
