from io import BytesIO
from pathlib import Path
from urllib.error import URLError

from src.installation import versioning


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_version_check_detects_newer_release(monkeypatch):
    monkeypatch.setattr(versioning, "urlopen", lambda *args, **kwargs: _Response(b'{"info":{"version":"0.3.0"}}'))
    status = versioning.check_latest_version("0.2.0")
    assert status.latest == "0.3.0"
    assert status.update_available is True
    assert status.source == "pypi"


def test_version_check_is_offline_safe(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(versioning, "urlopen", fail)
    status = versioning.check_latest_version("0.2.0")
    assert status.latest is None
    assert status.update_available is None
    assert status.source == "offline"


def test_installer_wires_hermes_and_runs_doctor():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "OPENBRAIN_INSTALL_HERMES" in script
    assert "openbrain install-hermes --force" in script
    assert "openbrain doctor" in script


def test_installer_preserves_isolation_and_supports_forks():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "OPENBRAIN_REPO_URL" in script
    assert 'pipx' in script
    assert 'install "git+$REPO_URL"' in script
