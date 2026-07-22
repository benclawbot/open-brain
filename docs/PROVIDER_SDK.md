# Open Brain Provider SDK

The provider SDK gives coding agents a small, stable integration surface without copying Hermes-specific code.

## Contract

Adapters expose a `ProviderDescriptor` and implement the `MemoryProvider` protocol:

- `health()` checks the Open Brain service;
- `recall()` requests a bounded actionable context packet;
- `remember()` writes one idempotent continuity event;
- `close()` releases transport resources.

The bundled `OpenBrainProviderClient` already implements this contract over REST.

## Minimal adapter

```python
from src.providers import (
    OpenBrainProviderClient,
    ProviderCapability,
    ProviderDescriptor,
    ProviderScope,
    RecallRequest,
    RememberRequest,
)

client = OpenBrainProviderClient(
    ProviderDescriptor(
        provider_id="medusa",
        display_name="Medusa",
        version="1.0.0",
        capabilities={
            ProviderCapability.RECALL,
            ProviderCapability.REMEMBER,
            ProviderCapability.SESSION_LIFECYCLE,
        },
    ),
    base_url="http://127.0.0.1:8000",
)

packet = client.recall(
    RecallRequest(
        scope=ProviderScope(project_id="00000000-0000-0000-0000-000000000001"),
        token_budget=1600,
        max_items=20,
    )
)

client.remember(
    RememberRequest(
        event_type="conversation.user_message",
        idempotency_key="medusa:session-42:message-18",
        payload={"content": "Continue the provider SDK implementation."},
    )
)
```

## Adapter rules

1. Use a stable lowercase `provider_id`; it becomes `source_system` on stored events.
2. Generate deterministic idempotency keys from the native session and record identifiers.
3. Preserve native identifiers in `source_record_id` or the event payload.
4. Mark direct user statements as `user_confirmed`; keep model-derived content as `provider_inference` or `assistant_claim`.
5. Do not silently swallow transport errors. A host may add an explicit spool, but replay must preserve the original idempotency key.
6. Keep agent-specific lifecycle mapping in the adapter and memory policy in Open Brain.

## Capability discovery

`ProviderDescriptor.capabilities` allows hosts and diagnostics to distinguish basic recall/remember adapters from integrations that also emit session, tool, delegation, compression, or offline-spool events.

## Current retrieval limitation

The current `/v1/context` endpoint accepts user, project, and task scope. Agent, workspace, and session identifiers remain valid for event ingestion, but are not yet direct context filters. The SDK intentionally omits unsupported fields from recall requests rather than sending invalid payloads.
