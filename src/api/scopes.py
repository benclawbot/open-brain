"""REST endpoints for canonical identity and Hermes session lineage."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from continuity.scopes import IdentityRecord, IdentityRef, SessionOpen, SessionRecord
from db.scope_queries import close_session, open_session, resolve_identity

router = APIRouter(prefix="/v1", tags=["scopes"])


class SessionClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str | None = Field(default=None, max_length=20000)


@router.post(
    "/identities/resolve",
    response_model=IdentityRecord,
    summary="Resolve a canonical identity and optional external alias",
)
async def resolve_identity_endpoint(identity: IdentityRef) -> IdentityRecord:
    try:
        return resolve_identity(identity)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/sessions/open",
    response_model=SessionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Idempotently open a Hermes session and preserve lineage",
)
async def open_session_endpoint(session: SessionOpen) -> SessionRecord:
    try:
        return open_session(session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/close",
    response_model=SessionRecord,
    summary="Close a continuity session without deleting its history",
)
async def close_session_endpoint(session_id: UUID, request: SessionClose) -> SessionRecord:
    try:
        record = close_session(session_id, request.summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return record
