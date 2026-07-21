"""REST endpoints for assertion lifecycle review proposals."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

try:
    from ..db.lifecycle_queries import (
        apply_lifecycle_proposal,
        generate_lifecycle_proposals,
        list_lifecycle_proposals,
        resolve_lifecycle_proposal,
        reverse_lifecycle_execution,
    )
    from ..lifecycle.execution import LifecycleExecutionError
except ImportError:  # Support legacy execution with src/ directly on sys.path.
    from db.lifecycle_queries import (
        apply_lifecycle_proposal,
        generate_lifecycle_proposals,
        list_lifecycle_proposals,
        resolve_lifecycle_proposal,
        reverse_lifecycle_execution,
    )
    from lifecycle.execution import LifecycleExecutionError

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


class ProposalGenerationRequest(BaseModel):
    limit: int = Field(default=250, ge=1, le=1000)
    minimum_score: float = Field(default=0.25, ge=0, le=1)


class ProposalReviewRequest(BaseModel):
    state: Literal["accepted", "rejected"]
    reviewed_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)


class ProposalApplyRequest(BaseModel):
    applied_by: str = Field(min_length=1, max_length=200)


class ProposalReverseRequest(BaseModel):
    reversed_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)


@router.post("/proposals/generate", status_code=status.HTTP_201_CREATED)
async def generate_proposals(request: ProposalGenerationRequest) -> dict:
    try:
        proposals = generate_lifecycle_proposals(limit=request.limit, minimum_score=request.minimum_score)
        return {"created": len(proposals), "proposals": proposals}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/proposals")
async def get_proposals(
    state: Literal["pending", "accepted", "rejected", "superseded"] = "pending",
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    try:
        return list_lifecycle_proposals(state=state, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/review")
async def review_proposal(proposal_id: UUID, request: ProposalReviewRequest) -> dict:
    try:
        proposal = resolve_lifecycle_proposal(
            proposal_id, state=request.state, reviewed_by=request.reviewed_by, note=request.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if proposal is None:
        raise HTTPException(status_code=404, detail="Pending lifecycle proposal not found")
    return proposal


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal(proposal_id: UUID, request: ProposalApplyRequest) -> dict:
    try:
        execution = apply_lifecycle_proposal(proposal_id, applied_by=request.applied_by)
    except LifecycleExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Lifecycle proposal not found")
    return execution


@router.post("/executions/{execution_id}/reverse")
async def reverse_execution(execution_id: UUID, request: ProposalReverseRequest) -> dict:
    try:
        execution = reverse_lifecycle_execution(
            execution_id, reversed_by=request.reversed_by, note=request.note
        )
    except LifecycleExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Lifecycle execution not found")
    return execution
