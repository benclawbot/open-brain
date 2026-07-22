"""REST endpoints for durable memory compaction."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.compaction_queries import compact_events

router = APIRouter(prefix="/compaction", tags=["compaction"])


class CompactionRequest(BaseModel):
    scope_type: Literal["user", "workspace", "session", "project", "task"]
    scope_id: UUID
    older_than_days: int = Field(default=14, ge=1, le=3650)
    minimum_events: int = Field(default=3, ge=2, le=1000)
    limit: int = Field(default=500, ge=1, le=5000)
    dry_run: bool = False


@router.post("/run")
async def run_compaction(request: CompactionRequest) -> dict:
    try:
        rows = compact_events(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"created": 0 if request.dry_run else len(rows), "candidates": rows}
