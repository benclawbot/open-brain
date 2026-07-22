"""Explicit Claude Code lifecycle bridge built on the universal provider SDK."""

from __future__ import annotations

import hashlib
from typing import Any

from src.providers import (
    OpenBrainProviderClient,
    ProviderCapability,
    ProviderDescriptor,
    RecallRequest,
    RememberRequest,
)

from .models import ClaudeSessionContext


class ClaudeSessionAdapter:
    """Normalize host-supplied Claude Code lifecycle events for Open Brain."""

    descriptor = ProviderDescriptor(
        provider_id="claude-code",
        display_name="Claude Code",
        version="1.0.0",
        capabilities={
            ProviderCapability.RECALL,
            ProviderCapability.REMEMBER,
            ProviderCapability.SESSION_LIFECYCLE,
            ProviderCapability.TOOL_EVENTS,
            ProviderCapability.COMPRESSION,
        },
    )

    def __init__(
        self,
        context: ClaudeSessionContext,
        *,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 3.0,
        client: OpenBrainProviderClient | None = None,
    ) -> None:
        self.context = context
        self.client = client or OpenBrainProviderClient(
            self.descriptor,
            base_url=base_url,
            timeout=timeout,
        )

    def health(self) -> dict[str, Any]:
        return self.client.health()

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        return self.client.recall(request.model_copy(update={"scope": self.context.scope}))

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        return self.client.remember(request.model_copy(update={"scope": self.context.scope}))

    def session_started(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._event("session.started", "start", metadata or {})

    def user_message(self, sequence: int, content: str) -> dict[str, Any]:
        return self._event(
            "conversation.user_message",
            f"user:{sequence}",
            {"content": content, "sequence": sequence},
            authority="user_confirmed",
        )

    def assistant_message(self, sequence: int, content: str) -> dict[str, Any]:
        return self._event(
            "conversation.assistant_message",
            f"assistant:{sequence}",
            {"content": content, "sequence": sequence},
            authority="assistant_claim",
        )

    def tool_result(
        self,
        sequence: int,
        tool: str,
        result: Any,
        *,
        success: bool,
    ) -> dict[str, Any]:
        return self._event(
            "tool.result",
            f"tool:{sequence}:{tool}",
            {"tool": tool, "result": result, "success": success, "sequence": sequence},
            authority="tool_observed",
        )

    def compressed(self, sequence: int, summary: str) -> dict[str, Any]:
        return self._event(
            "session.compressed",
            f"compression:{sequence}",
            {"summary": summary, "sequence": sequence},
            authority="curated_memory",
        )

    def session_ended(self, outcome: str | None = None) -> dict[str, Any]:
        return self._event("session.ended", "end", {"outcome": outcome})

    def close(self) -> None:
        self.client.close()

    def _event(
        self,
        event_type: str,
        record_key: str,
        payload: dict[str, Any],
        *,
        authority: str = "provider_inference",
    ) -> dict[str, Any]:
        return self.remember(
            RememberRequest(
                event_type=event_type,
                idempotency_key=self._idempotency_key(record_key),
                payload={
                    **payload,
                    "workspace_path": str(self.context.workspace_path),
                    "client_version": self.context.client_version,
                },
                authority=authority,
            )
        )

    def _idempotency_key(self, record_key: str) -> str:
        digest = hashlib.sha256(
            f"{self.context.session_key}:{record_key}".encode("utf-8")
        ).hexdigest()[:24]
        return f"claude-code:{digest}:{record_key}"[:512]
