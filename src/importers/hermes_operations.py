"""Discovery of Hermes procedural skills and scheduled jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from importers.base import ImportAdapter, ImportCandidate, ImportSource, hash_content


class HermesSkillImporter(ImportAdapter):
    """Import skill definitions as procedural candidates, never as plain facts."""

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir).expanduser()

    def source_fingerprint(self) -> str:
        if not self.skills_dir.exists():
            return hash_content(str(self.skills_dir.resolve()))
        parts = []
        for path in sorted(self.skills_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}:
                parts.append(str(path.resolve()).encode("utf-8") + b"\0" + path.read_bytes())
        return hash_content(b"\n".join(parts))

    def discover(self) -> Iterable[ImportCandidate]:
        if not self.skills_dir.exists():
            return []
        candidates = []
        for path in sorted(self.skills_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json"}:
                continue
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            relative = path.resolve().relative_to(self.skills_dir.resolve())
            candidates.append(
                ImportCandidate(
                    external_id=f"skill::{relative.as_posix()}",
                    external_hash=hash_content(content),
                    source=ImportSource.HERMES_SKILL,
                    content=content,
                    record_type="procedure",
                    authority="curated_memory",
                    metadata={
                        "source_path": str(path.resolve()),
                        "skill_name": path.stem,
                        "relative_path": relative.as_posix(),
                        "source_fingerprint": self.source_fingerprint(),
                        "requires_evaluation_before_activation": True,
                    },
                )
            )
        return candidates


class HermesCronImporter(ImportAdapter):
    """Import structured scheduled jobs while leaving Hermes as executor."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def source_fingerprint(self) -> str:
        content = self.path.read_bytes() if self.path.exists() else b""
        return hash_content(str(self.path.resolve()).encode("utf-8") + b"\0" + content)

    def discover(self) -> Iterable[ImportCandidate]:
        if not self.path.exists() or not self.path.is_file():
            return []
        value = json.loads(self.path.read_text(encoding="utf-8"))
        jobs = value.get("jobs", []) if isinstance(value, dict) else value
        if not isinstance(jobs, list):
            raise ValueError("cron export must be a list or contain a jobs list")

        candidates = []
        for ordinal, job in enumerate(jobs, start=1):
            if not isinstance(job, dict):
                continue
            external_id = str(job.get("id") or job.get("name") or ordinal)
            content = json.dumps(job, ensure_ascii=False, sort_keys=True)
            candidates.append(
                ImportCandidate(
                    external_id=f"cron::{external_id}",
                    external_hash=hash_content(content),
                    source=ImportSource.HERMES_CRON,
                    content=content,
                    record_type="automation",
                    authority="tool_observed",
                    metadata={
                        "source_path": str(self.path.resolve()),
                        "job_id": external_id,
                        "ordinal": ordinal,
                        "source_fingerprint": self.source_fingerprint(),
                        "executor": "hermes",
                    },
                )
            )
        return candidates
