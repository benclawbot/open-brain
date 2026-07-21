"""REST endpoints for previewing, staging, and rolling back imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from db.import_queries import rollback_staged_import
from importers.base import ImportSource
from importers.hermes_markdown import HermesMarkdownImporter
from importers.providers import provider_adapter, provider_descriptors
from importers.runner import ImportSummary, run_import

router = APIRouter(tags=["imports"])


class HermesMarkdownImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    source: ImportSource
    dry_run: bool = True
    resume_run_id: UUID | None = None


class ProviderImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    records: list[dict[str, Any]] = Field(min_length=1)
    source_instance: str | None = Field(default=None, max_length=512)
    dry_run: bool = True
    resume_run_id: UUID | None = None


class ImportRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=2000)


class ImportRollbackResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    status: str
    rolled_back_by: str
    rollback_reason: str
    rolled_back_records: int


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


@router.get(
    "/imports/providers",
    summary="List supported external memory-provider import capabilities",
)
async def list_provider_imports() -> list[dict[str, Any]]:
    return [descriptor.model_dump(mode="json") for descriptor in provider_descriptors()]


@router.post(
    "/imports/providers",
    response_model=ImportSummary,
    summary="Preview or stage normalized external memory-provider records",
)
async def import_provider_records(request: ProviderImportRequest) -> ImportSummary:
    try:
        adapter = provider_adapter(
            request.provider,
            request.records,
            source_instance=request.source_instance,
        )
        return run_import(
            adapter,
            source_system=f"memory_provider.{adapter.descriptor.name}",
            source_instance=request.source_instance,
            dry_run=request.dry_run,
            resume_run_id=request.resume_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/imports/{run_id}/rollback",
    response_model=ImportRollbackResponse,
    summary="Tombstone every unpromoted staged record in an import run",
)
async def rollback_import(run_id: UUID, request: ImportRollbackRequest) -> ImportRollbackResponse:
    try:
        result = rollback_staged_import(run_id, actor=request.actor, reason=request.reason)
        return ImportRollbackResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
