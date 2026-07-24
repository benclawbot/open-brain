"""REST endpoints for reviewed assertion pruning and restoration."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .proposals import ProposalActorRequest, ProposalReviewRequest
from ..db.pruning_queries import (
        apply_pruning_proposal,
        generate_pruning_proposals,
        list_pruning_proposals,
        restore_tombstone,
        review_pruning_proposal,
    )
from ..pruning.execution import PruningConflict

router = APIRouter(prefix="/pruning", tags=["pruning"])


class GenerateRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=2000)


@router.post("/proposals/generate", status_code=status.HTTP_201_CREATED)
async def generate(request: GenerateRequest) -> dict:
    try:
        proposals = generate_pruning_proposals(limit=request.limit)
        return {"created": len(proposals), "proposals": proposals}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/proposals")
async def list_proposals(
    state: Literal["pending", "accepted", "rejected", "applied", "reversed", "stale"] = "pending",
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    try:
        return list_pruning_proposals(state=state, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/review")
async def review(proposal_id: UUID, request: ProposalReviewRequest) -> dict:
    try:
        proposal = review_pruning_proposal(
            proposal_id, state=request.state, reviewed_by=request.reviewed_by, note=request.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if proposal is None:
        raise HTTPException(status_code=404, detail="Pending pruning proposal not found")
    return proposal


@router.post("/proposals/{proposal_id}/apply")
async def apply(proposal_id: UUID, request: ProposalActorRequest) -> dict:
    try:
        tombstone = apply_pruning_proposal(proposal_id, applied_by=request.actor)
    except (PruningConflict, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if tombstone is None:
        raise HTTPException(status_code=404, detail="Pruning proposal not found")
    return tombstone


@router.post("/tombstones/{tombstone_id}/restore")
async def restore(tombstone_id: UUID, request: ProposalActorRequest) -> dict:
    try:
        tombstone = restore_tombstone(
            tombstone_id, reversed_by=request.actor, note=request.note
        )
    except (PruningConflict, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if tombstone is None:
        raise HTTPException(status_code=404, detail="Tombstone not found")
    return tombstone
