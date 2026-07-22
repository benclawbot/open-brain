"""Install diagnostics and release checks."""

from __future__ import annotations

import json
import os
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from src.installation.versioning import check_latest_version


def installed_version() -> str:
    try:
        return version("openbrain")
    except PackageNotFoundError:
        return "development"


def version_check_cmd(*, as_json: bool = False) -> int:
    status = check_latest_version(installed_version())
    if as_json:
        print(json.dumps(status.as_dict(), indent=2))
    elif status.update_available is True:
        print(f"Update available: {status.installed} -> {status.latest}. Run `openbrain update`.")
    elif status.update_available is False:
        print(f"Open Brain is current ({status.installed}).")
    else:
        print(f"Could not check the latest release; installed version is {status.installed}.")
    return 0


def doctor_cmd(*, as_json: bool = False) -> int:
    hermes_home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    plugin_dir = hermes_home / "plugins" / "openbrain"
    checks = {
        "version": installed_version(),
        "python": shutil.which("python3") is not None,
        "pipx": shutil.which("pipx") is not None,
        "hermes": shutil.which("hermes") is not None,
        "hermes_plugin": plugin_dir.is_dir(),
        "database_url": bool(os.environ.get("DATABASE_URL")),
        "openbrain_url": os.environ.get("OPENBRAIN_URL"),
    }
    if as_json:
        print(json.dumps(checks, indent=2))
    else:
        for name, value in checks.items():
            print(f"{name}: {value}")
    required_ok = checks["python"] and checks["pipx"]
    return 0 if required_ok else 1
