"""REST endpoints for durable continuity operations."""

from fastapi import APIRouter, HTTPException, status

from api.consolidation import router as consolidation_router
from api.context import router as context_router
from api.imports import router as imports_router
from api.lifecycle import router as lifecycle_router
from api.scopes import router as scopes_router
from continuity.models import EventCreate, EventRecord
from db.continuity_queries import ingest_event

router = APIRouter(prefix="/v1", tags=["continuity"])
router.include_router(scopes_router)
router.include_router(imports_router)
router.include_router(context_router)
router.include_router(lifecycle_router)
router.include_router(consolidation_router)


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
