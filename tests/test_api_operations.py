import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.operations import (
    OperationalSettings,
    SlidingWindowLimiter,
    configure_operations,
)


def settings(**overrides):
    values = {
        "environment": "test",
        "api_key": "secret",
        "auth_required": True,
        "max_request_bytes": 32,
        "rate_limit_requests": 10,
        "rate_limit_window_seconds": 60,
        "trusted_proxy_headers": False,
    }
    values.update(overrides)
    return OperationalSettings(**values)


def make_app(config: OperationalSettings) -> FastAPI:
    app = FastAPI()
    configure_operations(app, config)

    @app.get("/health/live")
    async def live():
        return {"status": "healthy"}

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    @app.post("/protected")
    async def protected_post():
        return {"ok": True}

    return app


def test_production_requires_api_key(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENV", "production")
    monkeypatch.delenv("OPENBRAIN_API_KEY", raising=False)
    monkeypatch.delenv("OPENBRAIN_AUTH_REQUIRED", raising=False)

    with pytest.raises(RuntimeError, match="OPENBRAIN_API_KEY"):
        OperationalSettings.from_env()


def test_development_auth_is_opt_in(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENV", "development")
    monkeypatch.delenv("OPENBRAIN_API_KEY", raising=False)
    monkeypatch.delenv("OPENBRAIN_AUTH_REQUIRED", raising=False)

    loaded = OperationalSettings.from_env()

    assert loaded.auth_required is False


def test_public_probe_does_not_require_authentication():
    client = TestClient(make_app(settings()))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-request-id"]


def test_protected_route_accepts_bearer_or_api_key():
    client = TestClient(make_app(settings()))

    assert client.get("/protected").status_code == 401
    assert client.get(
        "/protected", headers={"Authorization": "Bearer secret"}
    ).status_code == 200
    assert client.get(
        "/protected", headers={"X-API-Key": "secret"}
    ).status_code == 200


def test_request_size_limit_rejects_before_handler():
    client = TestClient(make_app(settings(max_request_bytes=4)))

    response = client.post(
        "/protected",
        content=b"12345",
        headers={"X-API-Key": "secret", "Content-Type": "text/plain"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_rate_limiter_returns_retry_after():
    client = TestClient(
        make_app(settings(rate_limit_requests=1, rate_limit_window_seconds=60))
    )

    first = client.get("/health/live")
    second = client.get("/health/live")

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


def test_sliding_window_releases_expired_entries():
    limiter = SlidingWindowLimiter(requests=1, window_seconds=10)

    assert limiter.allow("client", now=0) == (True, 0)
    assert limiter.allow("client", now=1)[0] is False
    assert limiter.allow("client", now=11) == (True, 0)
