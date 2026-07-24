"""Safe import of Hermes USER.md, MEMORY.md, and context markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .base import (
    ImportAdapter,
    ImportCandidate,
    ImportSource,
    hash_content,
    stable_file_id,
)

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")


class HermesMarkdownImporter(ImportAdapter):
    """Parse curated Hermes markdown into provenance-rich candidates.

    The importer does not decide that every line is a durable fact. It emits
    candidates for later reconciliation and promotion while preserving the
    original file, section, ordinal, and content hash.
    """

    def __init__(self, path: str | Path, source: ImportSource):
        if source not in {
            ImportSource.HERMES_USER_MEMORY,
            ImportSource.HERMES_AGENT_MEMORY,
            ImportSource.HERMES_CONTEXT,
        }:
            raise ValueError("HermesMarkdownImporter only accepts markdown sources")
        self.path = Path(path).expanduser()
        self.source = source

    def source_fingerprint(self) -> str:
        resolved = self.path.resolve()
        content = self.path.read_bytes() if self.path.exists() else b""
        return hash_content(str(resolved).encode("utf-8") + b"\0" + content)

    def discover(self) -> Iterable[ImportCandidate]:
        if not self.path.exists():
            return []

        text = self.path.read_text(encoding="utf-8")
        section = "root"
        ordinal = 0
        candidates: list[ImportCandidate] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("<!--"):
                continue

            heading = _HEADING.match(line)
            if heading:
                section = heading.group(2).strip()
                continue

            list_item = _LIST_ITEM.match(raw_line)
            content = list_item.group(1).strip() if list_item else line
            if not content or content in {"---", "***", "___"}:
                continue

            ordinal += 1
            authority = (
                "curated_memory"
                if self.source
                in {
                    ImportSource.HERMES_USER_MEMORY,
                    ImportSource.HERMES_AGENT_MEMORY,
                }
                else "unknown"
            )
            record_type = "curated_memory_entry" if list_item else "markdown_paragraph"
            candidates.append(
                ImportCandidate(
                    external_id=stable_file_id(self.path, section, ordinal),
                    external_hash=hash_content(content),
                    source=self.source,
                    content=content,
                    record_type=record_type,
                    authority=authority,
                    metadata={
                        "source_path": str(self.path.resolve()),
                        "section": section,
                        "ordinal": ordinal,
                        "line_form": "list_item" if list_item else "paragraph",
                        "source_fingerprint": self.source_fingerprint(),
                    },
                )
            )

        return candidates


def discover_default_hermes_memory(hermes_home: str | Path) -> list[ImportCandidate]:
    """Discover built-in Hermes memory files without requiring either to exist."""
    home = Path(hermes_home).expanduser()
    discovered: list[ImportCandidate] = []
    sources = (
        (home / "USER.md", ImportSource.HERMES_USER_MEMORY),
        (home / "MEMORY.md", ImportSource.HERMES_AGENT_MEMORY),
    )
    for path, source in sources:
        discovered.extend(HermesMarkdownImporter(path, source).discover())
    return discovered
