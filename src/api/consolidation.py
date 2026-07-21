"""REST endpoints for assertion consolidation proposals."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

try:
    from ..db.consolidation_queries import (
        apply_consolidation_proposal,
        generate_consolidation_proposals,
        list_consolidation_proposals,
        resolve_consolidation_proposal,
        reverse_consolidation_execution,
    )
except ImportError:
    from db.consolidation_queries import (
        apply_consolidation_proposal,
        generate_consolidation_proposals,
        list_consolidation_proposals,
        resolve_consolidation_proposal,
        reverse_consolidation_execution,
    )

router = APIRouter(prefix="/consolidation", tags=["consolidation"])


class GenerationRequest(BaseModel):
    limit: int = Field(default=500, ge=2, le=2000)
    minimum_score: float = Field(default=0.5, ge=0, le=1)


class ReviewRequest(BaseModel):
    state: Literal["accepted", "rejected"]
    reviewed_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)


class ActorRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)


@router.post("/proposals/generate", status_code=status.HTTP_201_CREATED)
async def generate(request: GenerationRequest) -> dict:
    proposals = generate_consolidation_proposals(limit=request.limit, minimum_score=request.minimum_score)
    return {"created": len(proposals), "proposals": proposals}


@router.get("/proposals")
async def list_proposals(
    state: Literal["pending", "accepted", "rejected", "superseded"] = "pending",
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    return list_consolidation_proposals(state=state, limit=limit)


@router.post("/proposals/{proposal_id}/review")
async def review(proposal_id: UUID, request: ReviewRequest) -> dict:
    try:
        proposal = resolve_consolidation_proposal(
            proposal_id, state=request.state, reviewed_by=request.reviewed_by, note=request.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if proposal is None:
        raise HTTPException(status_code=404, detail="Pending consolidation proposal not found")
    return proposal


@router.post("/proposals/{proposal_id}/apply")
async def apply(proposal_id: UUID, request: ActorRequest) -> dict:
    try:
        execution = apply_consolidation_proposal(proposal_id, applied_by=request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Consolidation proposal not found")
    return execution


@router.post("/executions/{execution_id}/reverse")
async def reverse(execution_id: UUID, request: ActorRequest) -> dict:
    try:
        execution = reverse_consolidation_execution(
            execution_id, reversed_by=request.actor, note=request.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Consolidation execution not found")
    return execution
