"""
Open Brain REST API.
FastAPI server for memory and continuity operations.
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add src to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.continuity import router as continuity_router
from api.operations import configure_operations, database_readiness
from db.connection import init_db
from db.attribution import (
    search_memories,
    get_memory_by_id,
    insert_memory,
    get_recent_memories,
)
from db.queries import get_memory_stats
from embedder import create_embedding
from extractors.entities import extract_entities
from extractors.tagger import get_tagger
from analytics.trends import TrendAnalyzer
from analytics.weekly_report import generate_weekly_report

logger = logging.getLogger("openbrain.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize dependencies and retain a safe readiness signal."""
    app.state.startup_error = None
    try:
        init_db()
    except Exception as exc:
        app.state.startup_error = type(exc).__name__
        logger.exception("database initialization failed")
    yield


app = FastAPI(
    title="Open Brain API",
    description="REST API for memory management and durable agent continuity",
    version="0.2.0",
    lifespan=lifespan,
)
configure_operations(app)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "OPENBRAIN_CORS_ORIGINS",
        "http://localhost:8501,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

app.include_router(continuity_router)


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    source: str = "api"
    captured_by: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
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
    limit: int = Field(default=10, ge=1, le=100)
    sources: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    captured_by: Optional[List[str]] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Open Brain API",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/health/live")
async def health():
    """Liveness probe: the process and event loop are responsive."""
    return {"status": "healthy"}


@app.get("/health/ready")
async def readiness():
    """Readiness probe: startup and database dependencies are available."""
    startup_error = getattr(app.state, "startup_error", None)
    if startup_error:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependency": "database"},
        )
    ready, _error = database_readiness()
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependency": "database"},
        )
    return {"status": "ready"}


@app.get("/memories", response_model=List[MemoryResponse])
async def get_memories(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    captured_by: Optional[str] = None,
):
    """Get memories with optional transport and authoring-agent filters."""
    return get_recent_memories(limit, offset, source, captured_by)


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
    except Exception as exc:
        logger.warning("embedding creation failed: %s", type(exc).__name__)

    memory_id = insert_memory(
        source=source,
        captured_by=captured_by,
        content=content,
        embedding=embedding,
        entities=entities,
        tags=tags,
        tag_sources=tag_sources,
        importance=importance,
        metadata=metadata,
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {memory_id}") from exc
    memory = get_memory_by_id(parsed_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return memory


@app.post("/memories/search", response_model=List[MemoryResponse])
async def search_memories_endpoint(search: SearchRequest):
    """Search memories by semantic content and structured filters."""
    embedding = None
    if search.query:
        try:
            embedding = create_embedding(search.query)
        except Exception as exc:
            logger.warning("query embedding creation failed: %s", type(exc).__name__)

    results = search_memories(
        query=search.query,
        embedding=embedding,
        limit=search.limit,
        sources=search.sources,
        tags=search.tags,
        captured_by=search.captured_by,
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
    return get_memory_stats()


@app.get("/trends")
async def get_trends(weeks: int = Query(4, ge=1, le=12)):
    """Get trending topics."""
    analyzer = TrendAnalyzer()
    return {"trends": analyzer.get_top_trending(weeks)}


@app.get("/report/weekly")
async def get_weekly_report(days: int = Query(7, ge=1, le=30)):
    """Generate weekly report."""
    return {"report": generate_weekly_report(days)}
