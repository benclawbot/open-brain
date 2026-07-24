"""
conftest for tests/e2e/.

These tests need a running Open Brain stack (Postgres + api + ollama). The
test module itself auto-skips when the api is unreachable, but having a
conftest at this level lets a developer run only the e2e suite explicitly:

    pytest tests/e2e/ -v -s

and lets CI run the rest of the suite (unit tests) without needing the
stack up.
"""
import os
import pathlib
import urllib.request

import pytest


def _api_url() -> str:
    return os.environ.get("OPENBRAIN_E2E_URL", "http://127.0.0.1:8765").rstrip("/")


def _api_key() -> str | None:
    direct = os.environ.get("OPENBRAIN_E2E_KEY")
    if direct:
        return direct
    cfg = pathlib.Path.home() / ".config" / "openbrain" / ".env"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENBRAIN_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


@pytest.fixture(scope="session", autouse=True)
def require_openbrain_stack():
    """Skip every e2e test if the api or the api key is not available."""
    if not _api_key():
        pytest.skip("OPENBRAIN_API_KEY not set; e2e tests require a running stack")
    try:
        with urllib.request.urlopen(f"{_api_url()}/health", timeout=5) as r:
            healthy = r.status == 200
    except Exception:
        healthy = False
    if not healthy:
        pytest.skip(f"Open Brain api not reachable at {_api_url()}; bring up the stack first")
    yield
