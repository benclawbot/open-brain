"""REST endpoints for durable continuity event ingestion."""

from fastapi import APIRouter, HTTPException, status

from continuity.models import EventCreate, EventRecord
from db.continuity_queries import ingest_event

router = APIRouter(prefix="/v1", tags=["continuity"])


@router.post(
    "/events",
    response_model=EventRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an idempotent continuity event",
)
async def create_event(event: EventCreate) -> EventRecord:
    try:
        return ingest_event(event)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
