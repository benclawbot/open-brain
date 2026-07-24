"""Persistence operations for the additive continuity schema."""

from __future__ import annotations

import json
from typing import Any

from ..continuity.models import EventCreate, EventRecord, ScopeRef

from .connection import get_db_cursor


_EVENT_COLUMNS = """
    id, event_type, idempotency_key, source_system, source_record_id,
    user_identity_id, agent_identity_id, workspace_identity_id,
    session_id, project_id, task_id, causation_id, correlation_id,
    authority, sensitivity, retention_policy, payload,
    occurred_at, ingested_at
"""


def _row_to_event(row: dict[str, Any], *, duplicate: bool = False) -> EventRecord:
    payload = row.get("payload")
    if isinstance(payload, str):
        payload = json.loads(payload)

    return EventRecord(
        id=row["id"],
        event_type=row["event_type"],
        idempotency_key=row["idempotency_key"],
        source_system=row["source_system"],
        source_record_id=row.get("source_record_id"),
        scope=ScopeRef(
            user_identity_id=row.get("user_identity_id"),
            agent_identity_id=row.get("agent_identity_id"),
            workspace_identity_id=row.get("workspace_identity_id"),
            session_id=row.get("session_id"),
            project_id=row.get("project_id"),
            task_id=row.get("task_id"),
        ),
        causation_id=row.get("causation_id"),
        correlation_id=row.get("correlation_id"),
        authority=row["authority"],
        sensitivity=row["sensitivity"],
        retention_policy=row["retention_policy"],
        payload=payload or {},
        occurred_at=row["occurred_at"],
        ingested_at=row["ingested_at"],
        duplicate=duplicate,
    )


def ingest_event(event: EventCreate) -> EventRecord:
    """Insert an event exactly once and return the canonical stored record.

    Repeated requests with the same idempotency key return the existing event
    with ``duplicate=True``. The original payload is never silently replaced.
    """

    scope = event.scope
    with get_db_cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO event (
                event_type, idempotency_key, source_system, source_record_id,
                user_identity_id, agent_identity_id, workspace_identity_id,
                session_id, project_id, task_id, causation_id, correlation_id,
                authority, sensitivity, retention_policy, payload, occurred_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING {_EVENT_COLUMNS}
            """,
            (
                event.event_type,
                event.idempotency_key,
                event.source_system,
                event.source_record_id,
                scope.user_identity_id,
                scope.agent_identity_id,
                scope.workspace_identity_id,
                scope.session_id,
                scope.project_id,
                scope.task_id,
                event.causation_id,
                event.correlation_id,
                event.authority.value,
                event.sensitivity.value,
                event.retention_policy,
                json.dumps(event.payload),
                event.occurred_at,
            ),
        )
        inserted = cursor.fetchone()
        if inserted:
            return _row_to_event(dict(inserted))

        cursor.execute(
            f"SELECT {_EVENT_COLUMNS} FROM event WHERE idempotency_key = %s",
            (event.idempotency_key,),
        )
        existing = cursor.fetchone()
        if not existing:
            raise RuntimeError("idempotent event insert lost its canonical record")
        return _row_to_event(dict(existing), duplicate=True)


def get_event_by_idempotency_key(idempotency_key: str) -> EventRecord | None:
    with get_db_cursor() as cursor:
        cursor.execute(
            f"SELECT {_EVENT_COLUMNS} FROM event WHERE idempotency_key = %s",
            (idempotency_key,),
        )
        row = cursor.fetchone()
    return _row_to_event(dict(row)) if row else None
