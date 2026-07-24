"""Resolve the Open Brain release version from source or installed metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def get_version() -> str:
    """Return the project version in both source checkouts and installed wheels."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.is_file():
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        source_version = project.get("version")
        if isinstance(source_version, str) and source_version:
            return source_version

    try:
        return version("openbrain")
    except PackageNotFoundError:
        return "development"
