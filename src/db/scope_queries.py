"""Persistence for canonical identities and Hermes session lineage."""

from __future__ import annotations

import json
from uuid import UUID

from continuity.scopes import IdentityRecord, IdentityRef, SessionOpen, SessionRecord
from db.connection import get_db_cursor


def _json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value or {}


def resolve_identity(ref: IdentityRef) -> IdentityRecord:
    """Resolve an external alias first, otherwise upsert its canonical identity."""
    with get_db_cursor() as cursor:
        linked = False
        row = None
        if ref.external_id:
            cursor.execute(
                """
                SELECT i.*
                FROM identity_link l
                JOIN identity i ON i.id = l.canonical_identity_id
                WHERE l.source_system = %s
                  AND l.external_type = %s
                  AND l.external_id = %s
                """,
                (ref.source_system, ref.external_type, ref.external_id),
            )
            row = cursor.fetchone()
            linked = row is not None

        if row is None:
            cursor.execute(
                """
                INSERT INTO identity (kind, canonical_key, display_name, metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (kind, canonical_key) DO UPDATE SET
                    display_name = COALESCE(EXCLUDED.display_name, identity.display_name),
                    metadata = identity.metadata || EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    ref.kind.value,
                    ref.canonical_key,
                    ref.display_name,
                    json.dumps(ref.metadata),
                ),
            )
            row = cursor.fetchone()

        if ref.external_id:
            cursor.execute(
                """
                INSERT INTO identity_link (
                    canonical_identity_id, source_system, external_type,
                    external_id, metadata
                ) VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (source_system, external_type, external_id)
                DO UPDATE SET
                    canonical_identity_id = EXCLUDED.canonical_identity_id,
                    metadata = identity_link.metadata || EXCLUDED.metadata
                RETURNING id
                """,
                (
                    row["id"],
                    ref.source_system,
                    ref.external_type,
                    ref.external_id,
                    json.dumps(ref.metadata),
                ),
            )
            linked = True

    return IdentityRecord(
        **{
            **dict(row),
            "metadata": _json(row.get("metadata")),
            "linked": linked,
        }
    )


def get_session(source_system: str, external_session_id: str):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM session
            WHERE source_system = %s AND external_session_id = %s
            """,
            (source_system, external_session_id),
        )
        return cursor.fetchone()


def open_session(request: SessionOpen) -> SessionRecord:
    """Idempotently create or resolve a session with parent lineage."""
    user = resolve_identity(request.user) if request.user else None
    agent = resolve_identity(request.agent) if request.agent else None
    workspace = resolve_identity(request.workspace) if request.workspace else None

    parent_id: UUID | None = None
    if request.parent_external_session_id:
        parent = get_session(request.source_system, request.parent_external_session_id)
        if parent is None:
            raise ValueError(
                "parent session does not exist; import or open it before linking lineage"
            )
        parent_id = parent["id"]

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM session
            WHERE source_system = %s AND external_session_id = %s
            """,
            (request.source_system, request.external_session_id),
        )
        existing = cursor.fetchone()
        duplicate = existing is not None

        if existing is None:
            cursor.execute(
                """
                INSERT INTO session (
                    external_session_id, source_system, user_identity_id,
                    agent_identity_id, workspace_identity_id, project_id,
                    task_id, parent_session_id, lineage_reason, platform, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                RETURNING *
                """,
                (
                    request.external_session_id,
                    request.source_system,
                    user.id if user else None,
                    agent.id if agent else None,
                    workspace.id if workspace else None,
                    request.project_id,
                    request.task_id,
                    parent_id,
                    request.lineage_reason.value,
                    request.platform,
                    json.dumps(request.metadata),
                ),
            )
            row = cursor.fetchone()
        else:
            row = existing

    return SessionRecord(
        **{
            **dict(row),
            "metadata": _json(row.get("metadata")),
            "duplicate": duplicate,
        }
    )


def close_session(session_id: UUID, summary: str | None = None) -> SessionRecord | None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE session
            SET status = 'closed', ended_at = COALESCE(ended_at, NOW()),
                summary = COALESCE(%s, summary)
            WHERE id = %s
            RETURNING *
            """,
            (summary, session_id),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return SessionRecord(
        **{**dict(row), "metadata": _json(row.get("metadata")), "duplicate": False}
    )
