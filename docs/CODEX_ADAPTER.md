# Codex session bridge

Open Brain's Codex adapter is an explicit host bridge built on the universal provider SDK. It does not parse undocumented local transcript files or assume a particular Codex UI implementation.

## Integration pattern

Create one `CodexSessionAdapter` per host session and call it at stable lifecycle boundaries:

```python
from pathlib import Path

from src.openbrain_codex_adapter import CodexSessionAdapter, CodexSessionContext
from src.providers import ProviderScope, RecallRequest

adapter = CodexSessionAdapter(
    CodexSessionContext(
        session_key="stable-host-session-id",
        workspace_path=Path.cwd(),
        client_version="host-version",
        scope=ProviderScope(project_id=project_id),
    )
)

packet = adapter.recall(RecallRequest(token_budget=1600, max_items=20))
adapter.session_started()
adapter.user_message(1, user_text)
adapter.tool_result(2, "shell", result, success=True)
adapter.assistant_message(3, assistant_text)
adapter.session_ended("completed")
adapter.close()
```

## Event mapping

| Host boundary | Open Brain event | Authority |
|---|---|---|
| session start | `session.started` | provider inference |
| user message | `conversation.user_message` | user confirmed |
| assistant message | `conversation.assistant_message` | assistant claim |
| tool result | `tool.result` | tool observed |
| compression | `session.compressed` | curated memory |
| session end | `session.ended` | provider inference |

Identifiers are deterministic for a given session and record boundary, so repeated callbacks remain duplicate-safe.

## Conformance

The adapter is exercised through `run_provider_conformance()` in the test suite. Future host wrappers should preserve that gate and inject a mock transport or disposable Open Brain instance during CI.
