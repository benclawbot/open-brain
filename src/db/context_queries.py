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


def _assertion_id(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def save_context_feedback(packet_id: UUID, payload: dict) -> dict[str, int]:
    """Persist feedback and apply each packet item at most once to assertion counters."""
    summary = {"applied": 0, "duplicates": 0, "assertions_updated": 0}
    packet_id_value = str(packet_id)
    outcome = payload.get("outcome")

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

        for item in payload.get("items", []):
            context_item_id = str(item.get("context_item_id", ""))
            disposition = str(item.get("disposition", ""))
            assertion_id = _assertion_id(context_item_id)
            matched_assertion_id = None

            if assertion_id is not None:
                cursor.execute("SELECT id FROM assertion WHERE id = %s::uuid", (assertion_id,))
                row = cursor.fetchone()
                if row:
                    matched_assertion_id = str(row["id"])

            cursor.execute(
                """
                INSERT INTO context_feedback_application (
                    packet_id, context_item_id, disposition, assertion_id, note, outcome
                ) VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s)
                ON CONFLICT (packet_id, context_item_id) DO NOTHING
                RETURNING assertion_id
                """,
                (
                    packet_id_value,
                    context_item_id,
                    disposition,
                    matched_assertion_id,
                    item.get("note"),
                    outcome,
                ),
            )
            applied = cursor.fetchone()
            if applied is None:
                summary["duplicates"] += 1
                continue

            summary["applied"] += 1
            if matched_assertion_id is None:
                continue

            useful_increment = 1 if disposition == "used" else 0
            harmful_increment = 1 if disposition == "incorrect" else 0
            cursor.execute(
                """
                UPDATE assertion
                SET access_count = access_count + 1,
                    useful_count = useful_count + %s,
                    harmful_count = harmful_count + %s,
                    last_accessed_at = NOW()
                WHERE id = %s::uuid
                """,
                (useful_increment, harmful_increment, matched_assertion_id),
            )
            summary["assertions_updated"] += cursor.rowcount

    return summary
