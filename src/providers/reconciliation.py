"""Durable JSONL spool reconciliation for coding-agent adapters."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ReconcileResult:
    replayed: int = 0
    remaining: int = 0
    quarantined: int = 0
    dead_lettered: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "replayed": self.replayed,
            "remaining": self.remaining,
            "quarantined": self.quarantined,
            "dead_lettered": self.dead_lettered,
        }


class JsonlSpoolReconciler:
    """Replay a JSONL spool without losing records on partial failures.

    Each line is processed independently. Malformed records are quarantined,
    transient failures remain in the active spool with retry metadata, and
    records that exceed ``max_attempts`` move to a dead-letter file.
    Rewrites use ``os.replace`` so readers never observe a partially written file.
    """

    def __init__(self, path: Path, *, max_attempts: int = 5) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.path = path
        self.max_attempts = max_attempts

    @property
    def quarantine_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".quarantine")

    @property
    def dead_letter_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".dead")

    def replay(self, deliver: Callable[[dict[str, Any]], Any]) -> ReconcileResult:
        if not self.path.exists():
            return ReconcileResult()

        remaining: list[dict[str, Any]] = []
        quarantined: list[dict[str, Any]] = []
        dead_lettered: list[dict[str, Any]] = []
        replayed = 0

        for line_number, raw_line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
                if not isinstance(record, dict):
                    raise ValueError("record must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                quarantined.append(
                    {
                        "line": line_number,
                        "raw": raw_line,
                        "error": type(exc).__name__,
                        "quarantined_at": _utc_now(),
                    }
                )
                continue

            request_payload = {
                key: value
                for key, value in record.items()
                if key not in {"spooled_at", "attempts", "last_error", "last_attempt_at"}
            }
            try:
                deliver(request_payload)
                replayed += 1
            except Exception as exc:  # delivery policy belongs to the caller
                attempts = int(record.get("attempts", 0)) + 1
                failed = {
                    **record,
                    "attempts": attempts,
                    "last_error": type(exc).__name__,
                    "last_attempt_at": _utc_now(),
                }
                if attempts >= self.max_attempts:
                    failed["dead_lettered_at"] = _utc_now()
                    dead_lettered.append(failed)
                else:
                    remaining.append(failed)

        self._atomic_write(self.path, remaining)
        self._append_jsonl(self.quarantine_path, quarantined)
        self._append_jsonl(self.dead_letter_path, dead_lettered)
        return ReconcileResult(
            replayed=replayed,
            remaining=len(remaining),
            quarantined=len(quarantined),
            dead_lettered=len(dead_lettered),
        )

    @staticmethod
    def append(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @classmethod
    def _append_jsonl(cls, path: Path, records: list[dict[str, Any]]) -> None:
        for record in records:
            cls.append(path, record)

    @staticmethod
    def _atomic_write(path: Path, records: list[dict[str, Any]]) -> None:
        if not records:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            Path(temp_name).unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
