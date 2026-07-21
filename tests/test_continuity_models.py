from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.continuity.models import EventCreate, ScopeRef, TrustAuthority


def test_event_requires_namespaced_type():
    with pytest.raises(ValidationError):
        EventCreate(
            event_type="message",
            idempotency_key="hermes:test:0001",
            source_system="hermes",
            payload={"content": "hello"},
        )


def test_event_requires_timezone_aware_timestamp():
    with pytest.raises(ValidationError):
        EventCreate(
            event_type="conversation.user_message",
            idempotency_key="hermes:test:0002",
            source_system="hermes",
            payload={"content": "hello"},
            occurred_at=datetime(2026, 7, 21, 12, 0, 0),
        )


def test_event_preserves_scope_and_authority():
    project_id = uuid4()
    event = EventCreate(
        event_type="conversation.user_message",
        idempotency_key="hermes:test:0003",
        source_system="hermes",
        scope=ScopeRef(project_id=project_id),
        authority=TrustAuthority.USER_CONFIRMED,
        payload={"content": "Use upstream Hermes."},
        occurred_at=datetime.now(timezone.utc),
    )

    assert event.scope.project_id == project_id
    assert event.authority is TrustAuthority.USER_CONFIRMED
    assert event.event_type == "conversation.user_message"
