"""Operational security, limits, probes, and request diagnostics for the API."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..db.connection import get_db_cursor

logger = logging.getLogger("openbrain.api")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OperationalSettings:
    environment: str
    api_key: str | None
    auth_required: bool
    max_request_bytes: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    trusted_proxy_headers: bool

    @classmethod
    def from_env(cls) -> "OperationalSettings":
        environment = os.getenv("OPENBRAIN_ENV", "development").strip().lower()
        api_key = os.getenv("OPENBRAIN_API_KEY") or None
        production = environment in {"production", "prod"}
        auth_required = _env_bool("OPENBRAIN_AUTH_REQUIRED", production)
        if production and auth_required and not api_key:
            raise RuntimeError(
                "OPENBRAIN_API_KEY is required when authentication is enabled in production"
            )
        return cls(
            environment=environment,
            api_key=api_key,
            auth_required=auth_required,
            max_request_bytes=max(1, int(os.getenv("OPENBRAIN_MAX_REQUEST_BYTES", "1048576"))),
            rate_limit_requests=max(1, int(os.getenv("OPENBRAIN_RATE_LIMIT_REQUESTS", "120"))),
            rate_limit_window_seconds=max(
                1, int(os.getenv("OPENBRAIN_RATE_LIMIT_WINDOW_SECONDS", "60"))
            ),
            trusted_proxy_headers=_env_bool("OPENBRAIN_TRUST_PROXY_HEADERS", False),
        )


class SlidingWindowLimiter:
    """Small in-process limiter suitable for a single API process."""

    def __init__(self, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            entries = self._entries[key]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self.requests:
                retry_after = max(1, int(self.window_seconds - (current - entries[0])))
                return False, retry_after
            entries.append(current)
            return True, 0


def _client_key(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def _is_public_path(path: str) -> bool:
    return path in {"/", "/health", "/health/live", "/health/ready"}


def _valid_api_key(request: Request, expected: str | None) -> bool:
    if not expected:
        return False
    supplied = request.headers.get("x-api-key")
    authorization = request.headers.get("authorization", "")
    if not supplied and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def configure_operations(app: FastAPI, settings: OperationalSettings | None = None) -> None:
    settings = settings or OperationalSettings.from_env()
    limiter = SlidingWindowLimiter(
        settings.rate_limit_requests, settings.rate_limit_window_seconds
    )
    app.state.operational_settings = settings

    @app.middleware("http")
    async def operational_middleware(request: Request, call_next: Callable):
        started = time.monotonic()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        path = request.url.path

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large", "request_id": request_id},
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length", "request_id": request_id},
                    headers={"X-Request-ID": request_id},
                )

        client_key = _client_key(request, settings.trusted_proxy_headers)
        allowed, retry_after = limiter.allow(client_key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "request_id": request_id},
                headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
            )

        if settings.auth_required and not _is_public_path(path):
            if not _valid_api_key(request, settings.api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key", "request_id": request_id},
                    headers={
                        "WWW-Authenticate": "Bearer",
                        "X-Request-ID": request_id,
                    },
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "client_hash": hashlib.sha256(client_key.encode()).hexdigest()[:12],
                },
                sort_keys=True,
            )
        )
        return response


def database_readiness() -> tuple[bool, str | None]:
    """Verify that the database can serve a transaction without exposing secrets."""
    try:
        with get_db_cursor(dict_cursor=False) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, None
    except Exception as exc:  # pragma: no cover - exact driver failures vary
        logger.warning("database readiness failed: %s", type(exc).__name__)
        return False, type(exc).__name__
