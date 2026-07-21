"""Persistence primitives for resumable, provenance-preserving imports."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from db.connection import get_db_cursor
from importers.base import ImportCandidate


def create_import_run(
    source_system: str,
    source_instance: str | None,
    config: dict[str, Any],
    *,
    dry_run: bool,
    source_fingerprint: str | None = None,
) -> dict[str, Any]:
    run_config = {
        **config,
        "dry_run": dry_run,
        "source_fingerprint": source_fingerprint,
    }
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO import_run (source_system, source_instance, status, config)
            VALUES (%s, %s, 'running', %s::jsonb)
            RETURNING *
            """,
            (source_system, source_instance, json.dumps(run_config)),
        )
        return dict(cursor.fetchone())


def update_import_run(
    run_id: UUID,
    *,
    status: str,
    cursor_value: dict[str, Any] | None = None,
    records_seen: int | None = None,
    records_imported: int | None = None,
    records_merged: int | None = None,
    records_rejected: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE import_run
            SET status = %s,
                cursor = COALESCE(%s::jsonb, cursor),
                records_seen = COALESCE(%s, records_seen),
                records_imported = COALESCE(%s, records_imported),
                records_merged = COALESCE(%s, records_merged),
                records_rejected = COALESCE(%s, records_rejected),
                completed_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled')
                                    THEN NOW() ELSE completed_at END,
                error = %s
            WHERE id = %s
            RETURNING *
            """,
            (
                status,
                json.dumps(cursor_value) if cursor_value is not None else None,
                records_seen,
                records_imported,
                records_merged,
                records_rejected,
                status,
                error,
                run_id,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"import run not found: {run_id}")
        return dict(row)


def get_import_run(run_id: UUID) -> dict[str, Any] | None:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM import_run WHERE id = %s", (run_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


def record_import_candidate(
    run_id: UUID,
    candidate: ImportCandidate,
    *,
    operation: str,
    result: str,
    object_type: str | None = None,
    object_id: UUID | None = None,
    error: str | None = None,
) -> bool:
    """Record one source candidate. Returns False when already recorded in this run."""
    metadata = {
        **candidate.metadata,
        "source": candidate.source.value,
        "record_type": candidate.record_type,
        "authority": candidate.authority,
        "content": candidate.content,
    }
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO import_record (
                import_run_id, external_id, external_hash, object_type,
                object_id, operation, result, error, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (import_run_id, external_id, external_hash) DO NOTHING
            RETURNING id
            """,
            (
                run_id,
                candidate.external_id,
                candidate.external_hash,
                object_type,
                object_id,
                operation,
                result,
                error,
                json.dumps(metadata),
            ),
        )
        return cursor.fetchone() is not None


def seen_external_hashes(run_id: UUID) -> set[tuple[str, str]]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT external_id, external_hash
            FROM import_record
            WHERE import_run_id = %s
            """,
            (run_id,),
        )
        return {(row["external_id"], row["external_hash"]) for row in cursor.fetchall()}


def rollback_staged_import(
    run_id: UUID,
    *,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    """Tombstone every unpromoted staged record in an import run.

    Rollback is intentionally metadata-only: source data and audit records remain.
    Any record linked to a canonical object blocks rollback to avoid hiding promoted
    knowledge behind an import-level operation.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM import_run WHERE id = %s FOR UPDATE", (run_id,))
        run = cursor.fetchone()
        if run is None:
            raise ValueError(f"import run not found: {run_id}")

        config = run.get("config") or {}
        if isinstance(config, str):
            config = json.loads(config)
        if bool(config.get("dry_run")):
            raise ValueError("dry-run imports cannot be rolled back")
        if run.get("rolled_back_at") is not None:
            raise ValueError("import run is already rolled back")

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM import_record
            WHERE import_run_id = %s
              AND operation = 'stage'
              AND object_id IS NOT NULL
              AND rolled_back_at IS NULL
            """,
            (run_id,),
        )
        promoted = int(cursor.fetchone()["count"])
        if promoted:
            raise ValueError("import run contains promoted records and cannot be rolled back")

        tombstone = json.dumps({
            "kind": "staged_import_rollback",
            "actor": actor,
            "reason": reason,
        })
        cursor.execute(
            """
            UPDATE import_record
            SET rolled_back_at = NOW(),
                rolled_back_by = %s,
                rollback_reason = %s,
                tombstone = %s::jsonb,
                result = 'rolled_back'
            WHERE import_run_id = %s
              AND operation = 'stage'
              AND rolled_back_at IS NULL
            RETURNING id
            """,
            (actor, reason, tombstone, run_id),
        )
        rolled_back_records = len(cursor.fetchall())

        cursor.execute(
            """
            UPDATE import_run
            SET status = 'rolled_back',
                rolled_back_at = NOW(),
                rolled_back_by = %s,
                rollback_reason = %s
            WHERE id = %s
            RETURNING *
            """,
            (actor, reason, run_id),
        )
        updated = dict(cursor.fetchone())
        updated["rolled_back_records"] = rolled_back_records
        return updated
