"""Import Hermes session summaries and transcripts as episodic candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .base import ImportAdapter, ImportCandidate, ImportSource, hash_content


class HermesSessionImporter(ImportAdapter):
    """Discover JSON/JSONL session exports without promoting raw turns to facts."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def source_fingerprint(self) -> str:
        resolved = self.path.resolve()
        content = self.path.read_bytes() if self.path.exists() else b""
        return hash_content(str(resolved).encode("utf-8") + b"\0" + content)

    def discover(self) -> Iterable[ImportCandidate]:
        if not self.path.exists() or not self.path.is_file():
            return []
        suffix = self.path.suffix.lower()
        if suffix not in {".json", ".jsonl"}:
            raise ValueError("HermesSessionImporter accepts only .json or .jsonl")

        records = self._read_records(suffix)
        candidates: list[ImportCandidate] = []
        for ordinal, record in enumerate(records, start=1):
            session_id = str(record.get("session_id") or record.get("id") or ordinal)
            summary = record.get("summary")
            transcript = record.get("transcript") or record.get("messages")
            payload = summary if isinstance(summary, str) and summary.strip() else None
            record_type = "session_summary"
            if payload is None and transcript:
                payload = json.dumps(transcript, ensure_ascii=False, sort_keys=True)
                record_type = "session_transcript"
            if not payload:
                continue

            candidates.append(
                ImportCandidate(
                    external_id=f"{self.path.resolve()}::{session_id}",
                    external_hash=hash_content(payload),
                    source=ImportSource.HERMES_SESSION,
                    content=payload,
                    record_type=record_type,
                    authority="curated_memory" if record_type == "session_summary" else "unknown",
                    metadata={
                        "source_path": str(self.path.resolve()),
                        "session_id": session_id,
                        "ordinal": ordinal,
                        "source_fingerprint": self.source_fingerprint(),
                        "episodic": True,
                    },
                )
            )
        return candidates

    def _read_records(self, suffix: str) -> list[dict]:
        if suffix == ".jsonl":
            records = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(value)
            return records

        value = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            sessions = value.get("sessions")
            if isinstance(sessions, list):
                return [item for item in sessions if isinstance(item, dict)]
            return [value]
        return []
