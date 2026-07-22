"""Shared REST contracts for human-reviewed proposal workflows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProposalDecision = Literal["accepted", "rejected"]


class ProposalReviewRequest(BaseModel):
    """Explicit human decision for a pending proposal."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    state: ProposalDecision
    reviewed_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_rejection_note(self) -> "ProposalReviewRequest":
        if self.state == "rejected" and not self.note:
            raise ValueError("rejected proposals require a review note")
        return self


class ProposalActorRequest(BaseModel):
    """Actor attribution for applying or reversing an approved proposal."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    actor: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)
