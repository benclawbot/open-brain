"""Confine filesystem imports to explicit, operator-controlled roots.

The Hermes markdown importer reads a path supplied over HTTP. Without a
boundary, any caller that can reach the API can turn that endpoint into an
arbitrary file read. Callers must either point at the default Hermes/agent
homes or list additional roots in ``OPENBRAIN_IMPORT_ROOTS``.
"""

from __future__ import annotations

import os
from pathlib import Path

# Markdown import sources only. Restricting the suffix keeps credentials and
# binary blobs (``~/.ssh/id_rsa``, databases, keys) out of reach even when a
# directory happens to be allow-listed.
ALLOWED_IMPORT_SUFFIXES = frozenset({".md", ".markdown", ".txt"})

_DEFAULT_ROOT_NAMES = (".hermes", ".codex", ".claude")


class ImportPathError(ValueError):
    """Raised when an import path is missing, unsupported, or out of bounds."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def import_roots() -> list[Path]:
    """Return the resolved roots that imports may read from."""
    configured = os.getenv("OPENBRAIN_IMPORT_ROOTS", "").strip()
    if configured:
        raw_roots = [part for part in configured.split(os.pathsep) if part.strip()]
    else:
        raw_roots = [
            str(Path.home() / name)
            for name in _DEFAULT_ROOT_NAMES
        ]

    roots: list[Path] = []
    for raw in raw_roots:
        try:
            roots.append(Path(raw).expanduser().resolve())
        except OSError:
            # Unreadable or malformed roots are skipped rather than widening
            # the boundary to the current directory.
            continue
    return roots


def resolve_import_path(raw_path: str) -> Path:
    """Resolve *raw_path* and enforce the import boundary.

    Raises ``ImportPathError`` with a status code suitable for the API:
    404 when the file does not exist, 415 when the suffix is not importable,
    and 403 when the resolved path escapes every configured root.
    """
    try:
        path = Path(raw_path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ImportPathError("Source path is invalid", 400) from exc

    if not path.is_file():
        raise ImportPathError("Source file not found", 404)

    if path.suffix.lower() not in ALLOWED_IMPORT_SUFFIXES:
        raise ImportPathError(
            "Only markdown or text sources can be imported", 415
        )

    roots = import_roots()
    if not roots or not any(path.is_relative_to(root) for root in roots):
        raise ImportPathError(
            "Source path is outside the configured import roots", 403
        )

    return path
