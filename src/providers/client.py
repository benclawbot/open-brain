"""Generic REST client used by coding-agent provider adapters."""

from __future__ import annotations

from typing import Any

import httpx

from src.providers.contracts import ProviderDescriptor, RecallRequest, RememberRequest


class OpenBrainProviderClient:
    """Small synchronous client implementing the universal provider contract.

    The client owns its HTTP transport unless one is injected for tests or host
    lifecycle management. Errors remain explicit via ``httpx.HTTPStatusError``;
    adapters may layer spooling or fallback behavior without hidden data loss.
    """

    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.descriptor = descriptor
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "User-Agent": f"openbrain-provider/{descriptor.provider_id}/{descriptor.version}",
                "X-OpenBrain-Provider": descriptor.provider_id,
            },
        )

    def health(self) -> dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        payload = response.json()
        payload["provider"] = self.descriptor.model_dump(mode="json")
        return payload

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        payload = {
            "query": request.query,
            "token_budget": request.token_budget,
            "max_items": request.max_items,
            "include_stale": request.include_stale,
            **request.scope.model_dump(mode="json", exclude_none=True),
        }
        response = self._client.post("/v1/context", json=payload)
        response.raise_for_status()
        return response.json()

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        payload = {
            "event_type": request.event_type,
            "idempotency_key": request.idempotency_key,
            "source_system": self.descriptor.provider_id,
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
