"""Version discovery with explicit offline-safe results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from urllib.error import URLError
from urllib.request import urlopen

from packaging.version import InvalidVersion, Version

PYPI_JSON_URL = "https://pypi.org/pypi/openbrain/json"


@dataclass(frozen=True)
class VersionStatus:
    installed: str
    latest: str | None
    update_available: bool | None
    source: str
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def check_latest_version(installed: str, *, timeout: float = 3.0) -> VersionStatus:
    """Compare the installed release with PyPI without failing offline commands."""
    try:
        with urlopen(PYPI_JSON_URL, timeout=timeout) as response:  # noqa: S310 - fixed trusted URL
            payload = json.load(response)
        latest = str(payload["info"]["version"])
        update_available = Version(latest) > Version(installed)
        return VersionStatus(installed, latest, update_available, "pypi")
    except (URLError, TimeoutError, KeyError, ValueError, InvalidVersion) as exc:
        return VersionStatus(installed, None, None, "offline", str(exc))
