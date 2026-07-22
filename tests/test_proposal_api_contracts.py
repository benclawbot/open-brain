from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.proposals import ProposalActorRequest, ProposalReviewRequest


def test_acceptance_allows_optional_note() -> None:
    request = ProposalReviewRequest(state="accepted", reviewed_by="operator")

    assert request.state == "accepted"
    assert request.reviewed_by == "operator"
    assert request.note is None


def test_rejection_requires_explanation() -> None:
    with pytest.raises(ValidationError, match="rejected proposals require a review note"):
        ProposalReviewRequest(state="rejected", reviewed_by="operator")


def test_review_contract_strips_actor_and_note_whitespace() -> None:
    request = ProposalReviewRequest(
        state="rejected",
        reviewed_by="  operator  ",
        note="  stale evidence  ",
    )

    assert request.reviewed_by == "operator"
    assert request.note == "stale evidence"


def test_review_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProposalReviewRequest(
            state="accepted",
            reviewed_by="operator",
            unexpected=True,
        )


def test_actor_contract_requires_explicit_attribution() -> None:
    with pytest.raises(ValidationError):
        ProposalActorRequest(actor="   ")
