from datetime import datetime, timezone
from uuid import uuid4

from context.models import (
    ContextFeedback,
    ContextFeedbackItem,
    ContextItem,
    ContextKind,
    ContextPacket,
    ContextRequest,
    FeedbackDisposition,
    TrustLabel,
)


def test_context_request_enforces_budgets():
    request = ContextRequest(max_items=10, token_budget=800)
    assert request.max_items == 10
    assert request.token_budget == 800


def test_context_packet_preserves_trust_and_freshness():
    item = ContextItem(
        id="decision-1",
        kind=ContextKind.DECISION,
        text="Use upstream Hermes",
        trust=TrustLabel.USER_CONFIRMED,
        stale=False,
        observed_at=datetime.now(timezone.utc),
    )
    packet = ContextPacket(
        packet_id=uuid4(),
        scope_revisions={"project:1": 4},
        items=[item],
        estimated_tokens=12,
    )
    assert packet.items[0].trust is TrustLabel.USER_CONFIRMED
    assert packet.scope_revisions["project:1"] == 4


def test_feedback_contract_records_missing_context():
    feedback = ContextFeedback(
        packet_id=uuid4(),
        items=[
            ContextFeedbackItem(
                context_item_id="assertion-1",
                disposition=FeedbackDisposition.INCORRECT,
                note="Repository choice is stale",
            )
        ],
        missing=["latest upstream provider lifecycle"],
        outcome="recovered",
    )
    assert feedback.items[0].disposition is FeedbackDisposition.INCORRECT
    assert feedback.missing
