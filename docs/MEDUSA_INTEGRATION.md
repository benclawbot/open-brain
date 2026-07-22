# Medusa Integration

Open Brain ships a native Medusa adapter built on the universal provider SDK.
It keeps Open Brain optional: Medusa continues running when the service is unavailable,
while failed writes are durably spooled in the workspace.

## Setup

```python
from pathlib import Path

from src.openbrain_medusa_adapter import MedusaMemoryAdapter, MedusaSessionContext
from src.providers import ProviderScope

adapter = MedusaMemoryAdapter(
    MedusaSessionContext(
        session_key=session.id,
        workspace_path=Path(workspace.root),
        scope=ProviderScope(
            session_id=session.openbrain_session_id,
            project_id=workspace.openbrain_project_id,
        ),
        agent_version=MEDUSA_VERSION,
    ),
    base_url="http://127.0.0.1:8000",
)
```

## Lifecycle wiring

Call the adapter at Medusa's existing lifecycle boundaries:

```python
adapter.replay_spool()
context = adapter.recall(token_budget=1600, max_items=20)
adapter.session_started({"mode": session.mode})
adapter.user_message(sequence, text)
adapter.assistant_message(sequence, text)
adapter.tool_result(sequence, tool_name, result, success=success)
adapter.compression(sequence, summary)
adapter.delegation(sequence, target_agent, instruction)
adapter.session_ended(outcome)
adapter.close()
```

Inject `context.prompt_block` only when it is non-empty. Every item retains its
Open Brain kind and trust label so Medusa can distinguish confirmed decisions from
stale or inferred material.

## Durability

Failed writes are appended to:

```text
<workspace>/.medusa/openbrain-spool.jsonl
```

`replay_spool()` retries records with their original deterministic idempotency keys.
Successfully replayed entries are removed. Remaining failures stay in the spool.
Recall failures return an unavailable result and never fabricate context.

## Event mapping

| Medusa boundary | Open Brain event | Authority |
|---|---|---|
| session start | `session.started` | provider inference |
| user input | `conversation.user_message` | user confirmed |
| assistant output | `conversation.assistant_message` | assistant claim |
| tool completion | `tool.result` | tool observed |
| context compression | `session.compressed` | curated memory |
| sub-agent delegation | `agent.delegated` | provider inference |
| session close | `session.ended` | provider inference |

The adapter does not execute tools, alter Medusa approvals, or replace Medusa's own
session persistence. It only provides cross-agent continuity and durable evidence.
