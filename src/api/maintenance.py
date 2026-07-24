"""REST endpoint for bounded automated maintenance."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..maintenance import MaintenanceOptions, run_maintenance

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class MaintenanceRequest(BaseModel):
    dry_run: bool = True
    proposal_limit: int = Field(default=500, ge=1, le=2000)
    cache_max_rows: int = Field(default=5000, ge=1, le=100000)
    tombstone_retention_days: int = Field(default=90, ge=1, le=3650)
    compact_project_id: UUID | None = None
    compact_task_id: UUID | None = None
    compaction_min_events: int = Field(default=8, ge=2, le=2000)
    compaction_max_events: int = Field(default=200, ge=2, le=2000)


@router.post("/run")
async def run(request: MaintenanceRequest) -> dict:
    return run_maintenance(MaintenanceOptions(**request.model_dump()))
