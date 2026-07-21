"""REST endpoints for actionable context delivery and feedback."""

from fastapi import APIRouter, HTTPException

from context.builder import build_context_packet
from context.models import ContextFeedback, ContextPacket, ContextRequest
from db.context_queries import save_context_feedback

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
