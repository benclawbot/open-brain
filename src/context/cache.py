"""Revision-keyed cache helpers for context packet templates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

try:
    from .models import ContextPacket, ContextRequest
    from ..db.connection import get_db_cursor
except ImportError:  # Support legacy execution with src/ directly on sys.path.
    from context.models import ContextPacket, ContextRequest
    from db.connection import get_db_cursor

CACHE_TTL_SECONDS = 300
MAX_CACHE_ROWS = 5000


def request_fingerprint(request: ContextRequest) -> dict[str, Any]:
    return {
        "user_identity_id": str(request.user_identity_id) if request.user_identity_id else None,
        "project_id": str(request.project_id) if request.project_id else None,
        "task_id": str(request.task_id) if request.task_id else None,
        "max_items": request.max_items,
        "token_budget": request.token_budget,
        "include_history": request.include_history,
    }


def cache_key(request: ContextRequest, scope_revisions: dict[str, int]) -> str:
    payload = {
        "request": request_fingerprint(request),
        "scope_revisions": dict(sorted(scope_revisions.items())),
        "schema": 1,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def packet_template(packet: ContextPacket) -> dict[str, Any]:
    payload = packet.model_dump(mode="json")
    payload.pop("packet_id", None)
    payload.pop("generated_at", None)
    return payload


def hydrate_packet(template: dict[str, Any]) -> ContextPacket:
    return ContextPacket(
        packet_id=uuid4(),
        generated_at=datetime.now(timezone.utc),
        **template,
    )


def load_cached_packet(key: str) -> ContextPacket | None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE context_packet_cache
            SET hit_count = hit_count + 1, last_accessed_at = NOW()
            WHERE cache_key = %s AND expires_at > NOW()
            RETURNING packet_template
            """,
            (key,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return hydrate_packet(dict(row["packet_template"]))


def store_cached_packet(
    key: str,
    request: ContextRequest,
    scope_revisions: dict[str, int],
    packet: ContextPacket,
    *,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, ttl_seconds))
    template = packet_template(packet)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO context_packet_cache (
                cache_key, request_fingerprint, scope_revisions, packet_template,
                item_count, estimated_tokens, expires_at
            ) VALUES (%s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET
                request_fingerprint = EXCLUDED.request_fingerprint,
                scope_revisions = EXCLUDED.scope_revisions,
                packet_template = EXCLUDED.packet_template,
                item_count = EXCLUDED.item_count,
                estimated_tokens = EXCLUDED.estimated_tokens,
                created_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                last_accessed_at = NOW()
            """,
            (
                key,
                json.dumps(request_fingerprint(request)),
                json.dumps(scope_revisions),
                json.dumps(template),
                len(packet.items),
                packet.estimated_tokens,
                expires_at,
            ),
        )


def cleanup_context_cache(*, max_rows: int = MAX_CACHE_ROWS) -> dict[str, int]:
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM context_packet_cache WHERE expires_at <= NOW()")
        expired = cursor.rowcount
        cursor.execute(
            """
            DELETE FROM context_packet_cache
            WHERE cache_key IN (
                SELECT cache_key FROM context_packet_cache
                ORDER BY last_accessed_at DESC
                OFFSET %s
            )
            """,
            (max(1, max_rows),),
        )
        overflow = cursor.rowcount
    return {"expired": expired, "overflow": overflow}


def context_cache_stats() -> dict[str, int | float | None]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS rows,
                   COALESCE(SUM(hit_count), 0) AS hits,
                   COALESCE(SUM(item_count), 0) AS cached_items,
                   COALESCE(SUM(estimated_tokens), 0) AS cached_tokens,
                   MIN(expires_at) AS next_expiry
            FROM context_packet_cache
            WHERE expires_at > NOW()
            """
        )
        row = dict(cursor.fetchone())
    return {
        "rows": int(row["rows"]),
        "hits": int(row["hits"]),
        "cached_items": int(row["cached_items"]),
        "cached_tokens": int(row["cached_tokens"]),
        "next_expiry": row["next_expiry"].isoformat() if row.get("next_expiry") else None,
    }
