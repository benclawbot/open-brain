"""Explicitly allowlisted Hermes context-file discovery."""

from __future__ import annotations

from pathlib import Path

from importers.base import ImportCandidate, ImportSource, hash_content, stable_file_id
from importers.hermes_markdown import HermesMarkdownImporter

_ALLOWED_SUFFIXES = {".md", ".markdown", ".txt"}


def discover_allowlisted_context(
    hermes_home: str | Path,
    allowlist: list[str],
) -> list[ImportCandidate]:
    """Discover only explicitly named files rooted under ``hermes_home``.

    Paths that escape the Hermes root, are not regular files, or use unsupported
    suffixes are rejected. Nothing is discovered implicitly.
    """
    home = Path(hermes_home).expanduser().resolve()
    discovered: list[ImportCandidate] = []

    for relative in allowlist:
        candidate_path = (home / relative).resolve()
        try:
            candidate_path.relative_to(home)
        except ValueError as exc:
            raise ValueError(f"context path escapes Hermes home: {relative}") from exc

        if not candidate_path.exists() or not candidate_path.is_file():
            continue
        if candidate_path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ValueError(f"unsupported context file type: {candidate_path.suffix}")

        if candidate_path.suffix.lower() in {".md", ".markdown"}:
            markdown_candidates = HermesMarkdownImporter(
                candidate_path,
                ImportSource.HERMES_CONTEXT,
            ).discover()
            for candidate in markdown_candidates:
                candidate.metadata["allowlisted"] = True
                candidate.metadata["allowlist_entry"] = relative
                discovered.append(candidate)
            continue

        content = candidate_path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        discovered.append(
            ImportCandidate(
                external_id=stable_file_id(candidate_path, "root", 1),
                external_hash=hash_content(content),
                source=ImportSource.HERMES_CONTEXT,
                content=content,
                record_type="context_file",
                authority="unknown",
                metadata={
                    "source_path": str(candidate_path),
                    "source_fingerprint": hash_content(candidate_path.read_bytes()),
                    "allowlisted": True,
                    "allowlist_entry": relative,
                },
            )
        )

    return discovered
