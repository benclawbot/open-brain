"""Persistence and safe regeneration for event compactions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

try:
    from ..compaction.engine import (
        CompactionCandidate,
        POLICY_VERSION,
        build_summary,
        event_fingerprint,
        source_fingerprint,
    )
except ImportError:  # Support legacy execution with src/ directly on sys.path.
    from compaction.engine import (
        CompactionCandidate,
        POLICY_VERSION,
        build_summary,
        event_fingerprint,
        source_fingerprint,
    )

from .connection import get_db_cursor

_SCOPE_COLUMNS = {
    "user": "user_identity_id",
    "workspace": "workspace_identity_id",
    "session": "session_id",
    "project": "project_id",
    "task": "task_id",
}


def _candidate(row: dict[str, Any]) -> CompactionCandidate:
    payload = row.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    return CompactionCandidate(str(row["id"]), row["event_type"], payload, row["occurred_at"])


def compact_events(*, scope_type: str, scope_id: UUID, older_than_days: int = 14,
                   minimum_events: int = 3, limit: int = 500, dry_run: bool = False) -> list[dict[str, Any]]:
    column = _SCOPE_COLUMNS.get(scope_type)
    if column is None:
        raise ValueError("unsupported scope type")
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, older_than_days))
    with get_db_cursor() as cursor:
        cursor.execute(f"""
            SELECT id, event_type, payload, occurred_at
            FROM event
            WHERE {column}=%s AND occurred_at < %s
            ORDER BY event_type, occurred_at ASC, id ASC
            LIMIT %s
        """, (scope_id, cutoff, max(1, limit)))
        groups: dict[str, list[CompactionCandidate]] = {}
        for raw in cursor.fetchall():
            candidate = _candidate(dict(raw))
            groups.setdefault(candidate.event_type, []).append(candidate)

        results: list[dict[str, Any]] = []
        for event_type, candidates in groups.items():
            if len(candidates) < minimum_events:
                continue
            fingerprint = source_fingerprint(candidates)
            summary = build_summary(candidates)
            preview = {
                "scope_type": scope_type, "scope_id": str(scope_id), "event_type": event_type,
                "source_fingerprint": fingerprint, "source_event_count": len(candidates),
                "summary": summary, "dry_run": dry_run,
            }
            if dry_run:
                results.append(preview)
                continue
            cursor.execute("""
                INSERT INTO memory_compaction (
                    scope_type, scope_id, event_type, summary, source_fingerprint,
                    policy_version, source_event_count, first_occurred_at, last_occurred_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (scope_type, scope_id, event_type, source_fingerprint) DO NOTHING
                RETURNING *
            """, (scope_type, scope_id, event_type, summary, fingerprint, POLICY_VERSION,
                    len(candidates), candidates[0].occurred_at, candidates[-1].occurred_at))
            inserted = cursor.fetchone()
            if not inserted:
                continue
            compaction = dict(inserted)
            for candidate in candidates:
                cursor.execute("""
                    INSERT INTO memory_compaction_source (
                        compaction_id, event_id, event_fingerprint, occurred_at
                    ) VALUES (%s,%s,%s,%s)
                """, (compaction["id"], candidate.event_id, event_fingerprint(candidate), candidate.occurred_at))
            cursor.execute("""
                UPDATE memory_compaction
                SET status='superseded', superseded_by=%s
                WHERE scope_type=%s AND scope_id=%s AND event_type=%s
                  AND status='active' AND id<>%s
            """, (compaction["id"], scope_type, scope_id, event_type, compaction["id"]))
            results.append(compaction)
        return results


def fetch_active_compactions(*, project_id: UUID | None, task_id: UUID | None, limit: int = 20) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if project_id:
        clauses.append("(scope_type='project' AND scope_id=%s)")
        values.append(project_id)
    if task_id:
        clauses.append("(scope_type='task' AND scope_id=%s)")
        values.append(task_id)
    if not clauses:
        return []
    values.append(limit)
    with get_db_cursor() as cursor:
        cursor.execute(f"""
            SELECT * FROM memory_compaction
            WHERE status='active' AND ({' OR '.join(clauses)})
            ORDER BY last_occurred_at DESC LIMIT %s
        """, tuple(values))
        return [dict(row) for row in cursor.fetchall()]
