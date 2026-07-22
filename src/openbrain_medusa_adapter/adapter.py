"""Native Medusa lifecycle adapter for Open Brain."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx

from src.providers import (
    OpenBrainProviderClient,
    ProviderCapability,
    ProviderDescriptor,
    RecallRequest,
    RememberRequest,
)
from src.providers.reconciliation import JsonlSpoolReconciler

from .models import MedusaSessionContext, RecallResult


class MedusaMemoryAdapter:
    """Map Medusa lifecycle events to the universal provider SDK.

    Failed writes are appended to a local JSONL spool. Recall failures are soft so
    Medusa can continue operating without silently fabricating memory.
    """

    descriptor = ProviderDescriptor(
        provider_id="medusa",
        display_name="Medusa",
        version="1.0.0",
        capabilities={
            ProviderCapability.RECALL,
            ProviderCapability.REMEMBER,
            ProviderCapability.SESSION_LIFECYCLE,
            ProviderCapability.TOOL_EVENTS,
            ProviderCapability.DELEGATION,
            ProviderCapability.COMPRESSION,
            ProviderCapability.OFFLINE_SPOOL,
        },
    )

    def __init__(
        self,
        context: MedusaSessionContext,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        client: OpenBrainProviderClient | None = None,
    ) -> None:
        self.context = context
        self.client = client or OpenBrainProviderClient(
            self.descriptor,
            base_url=base_url,
            timeout=timeout,
        )

    def recall(self, *, token_budget: int = 1600, max_items: int = 20) -> RecallResult:
        try:
            packet = self.client.recall(
                RecallRequest(
                    scope=self.context.scope,
                    token_budget=token_budget,
                    max_items=max_items,
                    include_history=False,
                )
            )
        except (httpx.HTTPError, OSError):
            return RecallResult(unavailable=True)

        items = packet.get("items", [])
        lines = ["Open Brain continuity context:"]
        for item in items:
            trust = item.get("trust", "unknown")
            kind = item.get("kind", "context")
            text = str(item.get("text", "")).strip()
            if text:
                lines.append(f"- [{kind}; trust={trust}] {text}")
        return RecallResult(
            packet_id=packet.get("packet_id"),
            prompt_block="\n".join(lines) if len(lines) > 1 else "",
            item_count=len(lines) - 1,
        )

    def session_started(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._remember("session.started", "start", metadata or {})

    def user_message(self, sequence: int, content: str) -> dict[str, Any]:
        return self._remember(
            "conversation.user_message",
            f"user:{sequence}",
            {"content": content, "sequence": sequence},
            authority="user_confirmed",
        )

    def assistant_message(self, sequence: int, content: str) -> dict[str, Any]:
        return self._remember(
            "conversation.assistant_message",
            f"assistant:{sequence}",
            {"content": content, "sequence": sequence},
            authority="assistant_claim",
        )

    def tool_result(self, sequence: int, tool: str, result: Any, *, success: bool) -> dict[str, Any]:
        return self._remember(
            "tool.result",
            f"tool:{sequence}:{tool}",
            {"tool": tool, "result": result, "success": success, "sequence": sequence},
            authority="tool_observed",
        )

    def compression(self, sequence: int, summary: str) -> dict[str, Any]:
        return self._remember(
            "session.compressed",
            f"compression:{sequence}",
            {"summary": summary, "sequence": sequence},
            authority="curated_memory",
        )

    def delegation(self, sequence: int, target: str, instruction: str) -> dict[str, Any]:
        return self._remember(
            "agent.delegated",
            f"delegation:{sequence}:{target}",
            {"target": target, "instruction": instruction, "sequence": sequence},
        )

    def session_ended(self, outcome: str | None = None) -> dict[str, Any]:
        return self._remember("session.ended", "end", {"outcome": outcome})

    def replay_spool(self, *, max_attempts: int = 5) -> dict[str, int]:
        reconciler = JsonlSpoolReconciler(
            self.context.effective_spool_path(), max_attempts=max_attempts
        )

        def deliver(payload: dict[str, Any]) -> None:
            self.client.remember(RememberRequest.model_validate(payload))

        return reconciler.replay(deliver).as_dict()

    def close(self) -> None:
        self.client.close()

    def _remember(
        self,
        event_type: str,
        record_key: str,
        payload: dict[str, Any],
        *,
        authority: str = "provider_inference",
    ) -> dict[str, Any]:
        request = RememberRequest(
            event_type=event_type,
            idempotency_key=self._idempotency_key(record_key),
            payload={
                **payload,
                "workspace_path": str(self.context.workspace_path),
                "agent_version": self.context.agent_version,
            },
            scope=self.context.scope,
            authority=authority,
        )
        try:
            return self.client.remember(request)
        except (httpx.HTTPError, OSError) as exc:
            self._append_spool(request)
            return {"status": "spooled", "error": type(exc).__name__}

    def _idempotency_key(self, record_key: str) -> str:
        raw = f"{self.context.session_key}:{record_key}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"medusa:{digest}:{record_key}"[:512]

    def _append_spool(self, request: RememberRequest) -> None:
        record = request.model_dump(mode="json")
        record["spooled_at"] = datetime.now(timezone.utc).isoformat()
        JsonlSpoolReconciler.append(self.context.effective_spool_path(), record)
