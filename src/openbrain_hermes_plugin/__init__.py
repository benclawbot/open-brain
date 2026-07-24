"""Native Hermes memory provider for Open Brain."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


def _load_openbrain_environment() -> dict[str, str]:
    """Load the shared installer configuration without adding dependencies."""
    config_dir = Path(
        os.environ.get("OPENBRAIN_CONFIG_DIR", Path.home() / ".config" / "openbrain")
    ).expanduser()
    values = {
        "OPENBRAIN_URL": "http://127.0.0.1:8000",
        "OPENBRAIN_TIMEOUT": "3",
    }
    for path in (config_dir / ".env", Path.cwd() / ".env"):
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.removeprefix("export ").strip()
            if name.startswith("OPENBRAIN_"):
                values[name] = value.strip().strip("\"'")
    for name in tuple(values) + (
        "OPENBRAIN_API_KEY",
        "OPENBRAIN_PROJECT_ID",
        "OPENBRAIN_TASK_ID",
    ):
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def _digest(*parts: str) -> str:
    payload = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


class _Client:
    def __init__(
        self,
        base_url: str,
        timeout: float = 3.0,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def request(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None


class OpenBrainMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._client: _Client | None = None
        self._session_id = ""
        self._session_record_id: str | None = None
        self._platform = "cli"
        self._hermes_home = Path.home() / ".hermes"
        self._spool = self._hermes_home / "openbrain-spool.jsonl"
        self._cached_prefetch: dict[str, str] = {}
        self._prefetch_threads: dict[str, threading.Thread] = {}
        self._write_threads: list[threading.Thread] = []
        self._user_identity_id: str | None = None
        self._agent_identity_id: str | None = None
        self._workspace_identity_id: str | None = None
        self._project_id: str | None = None
        self._task_id: str | None = None

    @property
    def name(self) -> str:
        return "openbrain"

    def is_available(self) -> bool:
        return bool(_load_openbrain_environment()["OPENBRAIN_URL"].strip())

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._platform = str(kwargs.get("platform") or "cli")
        self._hermes_home = Path(kwargs.get("hermes_home") or Path.home() / ".hermes")
        self._spool = self._hermes_home / "openbrain-spool.jsonl"
        settings = _load_openbrain_environment()
        self._project_id = settings.get("OPENBRAIN_PROJECT_ID") or None
        self._task_id = settings.get("OPENBRAIN_TASK_ID") or None
        timeout = float(settings.get("OPENBRAIN_TIMEOUT", "3"))
        self._client = _Client(
            settings["OPENBRAIN_URL"],
            timeout,
            settings.get("OPENBRAIN_API_KEY"),
        )

        user_key = str(kwargs.get("user_id") or kwargs.get("user_id_alt") or "default-user")
        agent_key = str(kwargs.get("agent_identity") or "hermes")
        workspace_key = str(kwargs.get("agent_workspace") or "hermes")
        try:
            self._user_identity_id = self._resolve_identity("user", user_key, "platform_user", user_key)
            self._agent_identity_id = self._resolve_identity("agent", agent_key, "agent_profile", agent_key)
            self._workspace_identity_id = self._resolve_identity("workspace", workspace_key, "workspace", workspace_key)
            self._open_session(session_id, kwargs.get("parent_session_id") or "", "new")
            self._replay_spool()
        except Exception:
            logger.warning("Open Brain unavailable during initialization; continuing with local spool", exc_info=True)

    def _resolve_identity(self, kind: str, canonical_key: str, external_type: str, external_id: str) -> str:
        assert self._client
        response = self._client.request(
            "POST",
            "/v1/identities/resolve",
            {
                "kind": kind,
                "canonical_key": canonical_key,
                "source_system": "hermes",
                "external_type": external_type,
                "external_id": external_id,
            },
        )
        return str(response["id"])

    def _open_session(self, session_id: str, parent_session_id: str, reason: str) -> None:
        assert self._client
        payload: dict[str, Any] = {
            "external_session_id": session_id,
            "source_system": "hermes",
            "lineage_reason": reason,
            "platform": self._platform,
            "project_id": self._project_id,
            "task_id": self._task_id,
        }
        if parent_session_id:
            payload["parent_external_session_id"] = parent_session_id
        response = self._client.request("POST", "/v1/sessions/open", payload)
        self._session_record_id = str(response["id"])

    def system_prompt_block(self) -> str:
        return (
            "Open Brain is the active durable memory provider. Use recalled context only when relevant. "
            "Treat user-confirmed facts as higher authority than inferred or stale records."
        )

    def _recall(self, query: str, session_id: str) -> str:
        if not self._client:
            return ""
        sections: list[str] = []
        try:
            memories = self._client.request(
                "POST",
                "/memories/search",
                {"query": query, "limit": 8},
            ) or []
            lines = [f"- {item.get('content', '')}" for item in memories if item.get("content")]
            if lines:
                sections.append("## Relevant memories\n" + "\n".join(lines))
        except Exception:
            logger.debug("Open Brain semantic recall failed", exc_info=True)

        if self._project_id or self._task_id:
            try:
                packet = self._client.request(
                    "POST",
                    "/v1/context",
                    {
                        "user_identity_id": self._user_identity_id,
                        "project_id": self._project_id,
                        "task_id": self._task_id,
                        "max_items": 20,
                        "token_budget": 1600,
                    },
                ) or {}
                items = packet.get("items") or []
                lines = [
                    f"- [{item.get('trust', 'inferred')}] {item.get('text', '')}"
                    for item in items
                    if item.get("text")
                ]
                if lines:
                    sections.append("## Current work context\n" + "\n".join(lines))
            except Exception:
                logger.debug("Open Brain actionable context recall failed", exc_info=True)

        if not sections:
            return ""
        return "<openbrain-context>\n" + "\n\n".join(sections) + "\n</openbrain-context>"

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        key = session_id or self._session_id
        cached = self._cached_prefetch.pop(key, "")
        return cached or self._recall(query, key)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        key = session_id or self._session_id

        def worker() -> None:
            try:
                self._cached_prefetch[key] = self._recall(query, key)
            except Exception:
                logger.debug("Open Brain background prefetch failed", exc_info=True)

        thread = threading.Thread(target=worker, daemon=True)
        self._prefetch_threads[key] = thread
        thread.start()

    def _enqueue_event(self, event_type: str, payload: dict, *, authority: str = "tool_observed") -> None:
        event_payload = dict(payload)
        idempotency_key = event_payload.pop("idempotency_key")
        event = {
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "source_system": "hermes",
            "authority": authority,
            "scope": {
                "user_identity_id": self._user_identity_id,
                "agent_identity_id": self._agent_identity_id,
                "workspace_identity_id": self._workspace_identity_id,
                "session_id": self._session_record_id,
                "project_id": self._project_id,
                "task_id": self._task_id,
            },
            "payload": event_payload,
        }
        self._dispatch_or_spool("/v1/events", event)

    def _dispatch_or_spool(self, path: str, payload: dict) -> None:
        def worker() -> None:
            try:
                if not self._client:
                    raise RuntimeError("client unavailable")
                self._client.request("POST", path, payload)
            except Exception:
                self._spool.parent.mkdir(parents=True, exist_ok=True)
                with self._spool.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"path": path, "payload": payload}, sort_keys=True) + "\n")

        thread = threading.Thread(target=worker, daemon=True)
        self._write_threads.append(thread)
        thread.start()

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        sid = session_id or self._session_id
        key = f"hermes:{sid}:turn:{_digest(user_content, assistant_content)}"
        self._enqueue_event(
            "conversation.turn_completed",
            {
                "idempotency_key": key,
                "session_id": sid,
                "user_content": user_content,
                "assistant_content": assistant_content,
                "message_count": len(messages or []),
            },
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "openbrain_recall",
                "description": "Search durable Open Brain memory for relevant prior context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "openbrain_remember",
                "description": "Store a deliberate durable memory in Open Brain.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "importance": {"type": "number", "default": 0.7},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["content"],
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if not self._client:
            return json.dumps({"error": "Open Brain client unavailable"})
        try:
            if tool_name == "openbrain_recall":
                result = self._client.request(
                    "POST",
                    "/memories/search",
                    {"query": args["query"], "limit": int(args.get("limit", 8))},
                )
                return json.dumps(result)
            if tool_name == "openbrain_remember":
                result = self._client.request(
                    "POST",
                    "/memories",
                    {
                        "content": args["content"],
                        "source": "hermes",
                        "importance": float(args.get("importance", 0.7)),
                        "tags": list(args.get("tags") or []),
                    },
                )
                return json.dumps(result)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs,
    ) -> None:
        reason = "rewind" if rewound else "reset" if reset else "branch" if parent_session_id else "new"
        try:
            self._open_session(new_session_id, parent_session_id, reason)
        except Exception:
            logger.warning("Failed to record Open Brain session switch", exc_info=True)
            self._session_record_id = None
        self._session_id = new_session_id
        self._cached_prefetch.pop(new_session_id, None)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        self._enqueue_event(
            "session.pre_compress",
            {
                "idempotency_key": f"hermes:{self._session_id}:pre-compress:{len(messages)}",
                "session_id": self._session_id,
                "message_count": len(messages),
            },
        )
        return "Preserve explicit user corrections, decisions, unresolved commitments, and reusable lessons."

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._enqueue_event(
            "memory.builtin_write",
            {
                "idempotency_key": f"hermes:{self._session_id}:memory:{target}:{action}:{_digest(content)}",
                "action": action,
                "target": target,
                "content": content,
                "metadata": metadata or {},
            },
            authority="curated_memory",
        )

    def on_delegation(
        self,
        task: str,
        result: str,
        *,
        child_session_id: str = "",
        **kwargs,
    ) -> None:
        self._enqueue_event(
            "agent.delegation_completed",
            {
                "idempotency_key": (
                    f"hermes:{self._session_id}:delegation:{child_session_id}:{_digest(task, result)}"
                ),
                "task": task,
                "result": result,
                "child_session_id": child_session_id,
            },
        )

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        self._enqueue_event(
            "session.ended",
            {
                "idempotency_key": f"hermes:{self._session_id}:ended:{len(messages)}",
                "session_id": self._session_id,
                "message_count": len(messages),
            },
        )

    def _replay_spool(self) -> None:
        if not self._client or not self._spool.exists():
            return
        remaining: list[str] = []
        for line in self._spool.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                self._client.request("POST", item["path"], item["payload"])
            except Exception:
                remaining.append(line)
        if remaining:
            self._spool.write_text("\n".join(remaining) + "\n", encoding="utf-8")
        else:
            self._spool.unlink(missing_ok=True)

    def shutdown(self) -> None:
        for thread in list(self._write_threads):
            thread.join(timeout=2.0)
        try:
            self._replay_spool()
        except Exception:
            logger.debug("Open Brain spool replay failed during shutdown", exc_info=True)

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "url",
                "description": "Open Brain REST API URL",
                "default": "http://127.0.0.1:8000",
                "required": True,
                "env_var": "OPENBRAIN_URL",
            }
        ]

    def backup_paths(self) -> List[str]:
        home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
        return [str(home / "openbrain-spool.jsonl")]


def register(ctx) -> None:
    ctx.register_memory_provider(OpenBrainMemoryProvider())
