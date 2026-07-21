"""Structured context retrieval, revision tracking, and feedback persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from db.connection import get_db_cursor


def get_scope_revisions(user_identity_id: UUID | None, project_id: UUID | None, task_id: UUID | None) -> dict[str, int]:
    scopes: list[tuple[str, UUID]] = []
    if user_identity_id:
        scopes.append(("user", user_identity_id))
    if project_id:
        scopes.append(("project", project_id))
    if task_id:
        scopes.append(("task", task_id))
    if not scopes:
        return {}

    revisions: dict[str, int] = {}
    with get_db_cursor() as cursor:
        for scope_type, scope_id in scopes:
            cursor.execute(
                """
                INSERT INTO context_revision (scope_type, scope_id, revision)
                VALUES (%s, %s, 1)
                ON CONFLICT (scope_type, scope_id) DO NOTHING
                """,
                (scope_type, scope_id),
            )
            cursor.execute(
                "SELECT revision FROM context_revision WHERE scope_type = %s AND scope_id = %s",
                (scope_type, scope_id),
            )
            revisions[f"{scope_type}:{scope_id}"] = int(cursor.fetchone()["revision"])
    return revisions


def increment_scope_revision(scope_type: str, scope_id: UUID) -> int:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO context_revision (scope_type, scope_id, revision)
            VALUES (%s, %s, 1)
            ON CONFLICT (scope_type, scope_id) DO UPDATE SET
                revision = context_revision.revision + 1,
                updated_at = NOW()
            RETURNING revision
            """,
            (scope_type, scope_id),
        )
        return int(cursor.fetchone()["revision"])


def fetch_structured_context(project_id: UUID | None, task_id: UUID | None, include_history: bool, limit: int) -> dict:
    data: dict[str, list[dict] | dict | None] = {
        "project": None,
        "tasks": [],
        "decisions": [],
        "assertions": [],
        "outcomes": [],
    }
    with get_db_cursor() as cursor:
        if project_id:
            cursor.execute("SELECT * FROM project WHERE id = %s", (project_id,))
            row = cursor.fetchone()
            data["project"] = dict(row) if row else None

            cursor.execute(
                """
                SELECT * FROM task
                WHERE project_id = %s
                  AND (%s OR status NOT IN ('completed', 'cancelled', 'archived'))
                ORDER BY priority DESC, updated_at DESC
                LIMIT %s
                """,
                (project_id, include_history, limit),
            )
            data["tasks"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT * FROM decision
                WHERE project_id = %s AND (%s OR status = 'active')
                ORDER BY decided_at DESC
                LIMIT %s
                """,
                (project_id, include_history, limit),
            )
            data["decisions"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT * FROM outcome
                WHERE project_id = %s
                ORDER BY occurred_at DESC
                LIMIT %s
                """,
                (project_id, limit),
            )
            data["outcomes"] = [dict(row) for row in cursor.fetchall()]

        subject_ids = [value for value in (project_id, task_id) if value]
        if subject_ids:
            cursor.execute(
                """
                SELECT * FROM assertion
                WHERE subject_id = ANY(%s)
                  AND (%s OR status IN ('active', 'confirmed'))
                ORDER BY importance DESC, last_confirmed_at DESC NULLS LAST, last_observed_at DESC
                LIMIT %s
                """,
                (subject_ids, include_history, limit),
            )
            data["assertions"] = [dict(row) for row in cursor.fetchall()]

        if task_id and not any(str(row.get("id")) == str(task_id) for row in data["tasks"]):
            cursor.execute("SELECT * FROM task WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            if row:
                data["tasks"] = [dict(row), *data["tasks"]]
    return data


def save_context_feedback(packet_id: UUID, payload: dict) -> None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO event (
                event_type, idempotency_key, source_system, authority,
                sensitivity, retention_policy, payload, occurred_at
            ) VALUES (
                'context.feedback', %s, 'openbrain.api', 'tool_observed',
                'normal', 'default', %s::jsonb, %s
            ) ON CONFLICT (idempotency_key) DO UPDATE SET payload = EXCLUDED.payload
            """,
            (f"context-feedback:{packet_id}", json.dumps(payload), datetime.now(timezone.utc)),
        )
