"""Shared embedding regeneration workflow for REST and MCP surfaces."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from .db.attribution import get_memory_embedding_target, update_memory_embedding
from .embedder import create_embedding


def regenerate_memory_embedding(
    memory_id: uuid.UUID,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Regenerate one memory embedding without changing memory identity or timestamps.

    By default an existing embedding is left untouched. ``force=True`` is intended
    for embedding provider/model migrations where all stored vectors must be rebuilt.
    """
    target = get_memory_embedding_target(memory_id)
    if target is None:
        raise KeyError(str(memory_id))

    if target["has_embedding"] and not force:
        return {
            "id": str(memory_id),
            "status": "unchanged",
            "reason": "embedding_exists",
        }

    embedding = create_embedding(target["content"])
    updated = update_memory_embedding(memory_id, embedding, force=force)
    if not updated:
        # A concurrent writer may have filled a NULL embedding after our read.
        return {
            "id": str(memory_id),
            "status": "unchanged",
            "reason": "embedding_exists",
        }

    return {
        "id": str(memory_id),
        "status": "regenerated",
        "force": force,
    }
