"""REST endpoints for previewing and staging Hermes bootstrap imports."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from importers.base import ImportSource
from importers.hermes_markdown import HermesMarkdownImporter
from importers.runner import ImportSummary, run_import

router = APIRouter(tags=["imports"])


class HermesMarkdownImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    source: ImportSource
    dry_run: bool = True
    resume_run_id: UUID | None = None


@router.post(
    "/imports/hermes/markdown",
    response_model=ImportSummary,
    summary="Preview or stage a resumable Hermes markdown import",
)
async def import_hermes_markdown(request: HermesMarkdownImportRequest) -> ImportSummary:
    if request.source not in {
        ImportSource.HERMES_USER_MEMORY,
        ImportSource.HERMES_AGENT_MEMORY,
        ImportSource.HERMES_CONTEXT,
    }:
        raise HTTPException(status_code=422, detail="source must be a Hermes markdown source")

    path = Path(request.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"source file not found: {path}")

    try:
        return run_import(
            HermesMarkdownImporter(path, request.source),
            source_system=request.source.value,
            source_instance=str(path.resolve()),
            dry_run=request.dry_run,
            resume_run_id=request.resume_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
