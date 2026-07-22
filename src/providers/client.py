"""Generic REST client used by coding-agent provider adapters."""

from __future__ import annotations

from typing import Any

import httpx

from src.providers.contracts import ProviderDescriptor, RecallRequest, RememberRequest
from src.providers.host_config import HostAdapterConfig


class OpenBrainProviderClient:
    """Small synchronous client implementing the universal provider contract.

    Connection settings default to ``OPENBRAIN_URL``, ``OPENBRAIN_API_KEY``, and
    ``OPENBRAIN_TIMEOUT`` so installed hosts work without bespoke Python wiring.
    Explicit constructor values remain available for embedding and tests.
    """

    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.descriptor = descriptor
        self._owns_client = client is None
        config = HostAdapterConfig.from_env()
        resolved = HostAdapterConfig(
            base_url=(base_url or config.base_url).rstrip("/"),
            timeout=timeout if timeout is not None else config.timeout,
            api_key=api_key if api_key is not None else config.api_key,
        )
        self._client = client or httpx.Client(
            base_url=resolved.base_url,
            timeout=resolved.timeout,
            headers=resolved.headers(descriptor.provider_id, descriptor.version),
        )

    def health(self) -> dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        payload = response.json()
        payload["provider"] = self.descriptor.model_dump(mode="json")
        return payload

    def ready(self) -> dict[str, Any]:
        response = self._client.get("/ready")
        response.raise_for_status()
        payload = response.json()
        payload["provider"] = self.descriptor.model_dump(mode="json")
        return payload

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        scope = request.scope
        payload = {
            "user_identity_id": str(scope.user_identity_id) if scope.user_identity_id else None,
            "project_id": str(scope.project_id) if scope.project_id else None,
            "task_id": str(scope.task_id) if scope.task_id else None,
            "token_budget": request.token_budget,
            "max_items": request.max_items,
            "include_history": request.include_history,
        }
        response = self._client.post(
            "/v1/context",
            json={key: value for key, value in payload.items() if value is not None},
        )
        response.raise_for_status()
        return response.json()

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        payload = {
            "event_type": request.event_type,
            "idempotency_key": request.idempotency_key,
            "source_system": self.descriptor.provider_id,
            "captured_by": self.descriptor.provider_id,
            "source_record_id": request.source_record_id,
            "scope": request.scope.model_dump(mode="json", exclude_none=True),
            "authority": request.authority.value,
            "sensitivity": request.sensitivity.value,
            "retention_policy": request.retention_policy,
            "payload": request.payload,
        }
        response = self._client.post("/v1/events", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenBrainProviderClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
