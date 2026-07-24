"""REST endpoints for actionable context delivery, feedback, and cache operations."""

from fastapi import APIRouter, HTTPException, Query

from ..context.builder import build_context_packet
from ..context.cache import cleanup_context_cache, context_cache_stats
from ..context.models import ContextFeedback, ContextPacket, ContextRequest
from ..db.context_queries import save_context_feedback

router = APIRouter(tags=["context"])


@router.post("/context", response_model=ContextPacket)
async def create_context_packet(request: ContextRequest) -> ContextPacket:
    try:
        return build_context_packet(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/context/feedback", status_code=204)
async def submit_context_feedback(feedback: ContextFeedback) -> None:
    try:
        save_context_feedback(feedback.packet_id, feedback.model_dump(mode="json"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/context/cache/stats")
async def get_context_cache_stats() -> dict:
    try:
        return context_cache_stats()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/context/cache/cleanup")
async def cleanup_context_packet_cache(
    max_rows: int = Query(default=5000, ge=100, le=100000),
) -> dict[str, int]:
    try:
        return cleanup_context_cache(max_rows=max_rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
