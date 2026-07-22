"""Pure compaction policy and deterministic summary construction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

POLICY_VERSION = "event-rollup-v1"


@dataclass(frozen=True, slots=True)
class CompactionCandidate:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def event_fingerprint(candidate: CompactionCandidate) -> str:
    raw = f"{candidate.event_id}\n{candidate.event_type}\n{candidate.occurred_at.isoformat()}\n{canonical_payload(candidate.payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_fingerprint(candidates: list[CompactionCandidate]) -> str:
    fingerprints = sorted(event_fingerprint(candidate) for candidate in candidates)
    return hashlib.sha256((POLICY_VERSION + "\n" + "\n".join(fingerprints)).encode("utf-8")).hexdigest()


def _payload_text(payload: dict[str, Any]) -> str:
    for key in ("summary", "content", "message", "result", "title", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return canonical_payload(payload)


def build_summary(candidates: list[CompactionCandidate], *, max_examples: int = 5) -> str:
    if not candidates:
        raise ValueError("at least one source event is required")
    ordered = sorted(candidates, key=lambda item: (item.occurred_at, item.event_id))
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in reversed(ordered):
        text = _payload_text(candidate.payload)
        if text in seen:
            continue
        seen.add(text)
        unique.append(text)
        if len(unique) >= max_examples:
            break
    unique.reverse()
    first = ordered[0].occurred_at.isoformat()
    last = ordered[-1].occurred_at.isoformat()
    details = "; ".join(unique)
    return f"{len(ordered)} {ordered[0].event_type} events from {first} through {last}. Recent distinct details: {details}"
