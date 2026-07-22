# Claude Code adapter

`ClaudeSessionAdapter` connects explicit Claude Code host lifecycle callbacks to Open Brain without parsing private or undocumented transcript files.

The host supplies a stable session key, workspace path, client version, and canonical Open Brain scope. It should call:

- `session_started()` when a session opens
- `user_message()` and `assistant_message()` at message boundaries
- `tool_result()` after a completed tool call
- `compressed()` when context is summarized
- `session_ended()` during orderly shutdown

Recall and remember operations always use the context scope, preventing callers from accidentally writing across projects. Event identities are deterministic per session and lifecycle boundary, so repeated callbacks remain duplicate-safe.

The adapter implements the public `MemoryProvider` protocol and is validated with `run_provider_conformance()`.
