# Open Brain × Hermes Integration Architecture

Status: accepted implementation baseline

## Purpose

Open Brain is the user-owned continuity, evidence, knowledge, and improvement substrate. Hermes remains the active agent runtime, interface, scheduler, tool user, and communicator.

The integration must make knowledge portable across models and interfaces without placing Open Brain on Hermes' critical execution path.

## Non-negotiable decisions

- Integrate against the current upstream `NousResearch/hermes-agent`, never the stale `benclawbot/hermes-agent` fork.
- Use a native Hermes `MemoryProvider` plugin for lifecycle integration.
- Keep Open Brain's MCP server for Medusa, Claude, Codex, and other clients.
- Preserve Hermes built-in `USER.md` and `MEMORY.md`; import them initially and mirror later writes.
- Treat external providers such as Honcho, Mem0, and Hindsight as import/enrichment sources, not canonical truth.
- Never flatten user statements, assistant claims, provider inferences, summaries, and tool observations into equal memories.
- Keep expensive extraction, embedding, consolidation, provider synchronization, and improvement analysis asynchronous.
- Prefer demotion and archival over deletion. User-authored knowledge is never deleted by an automated quality heuristic.

## System relationship

```text
Telegram / Slack / CLI / Desktop
                |
                v
             Hermes
 models · tools · skills · cron · computer use
                |
        native MemoryProvider
                |
                v
            Open Brain
 evidence · identity · sessions · projects · tasks
 decisions · assertions · outcomes · improvements
                |
       REST/event API + MCP API
                |
        Medusa / other agents
```

## Storage layers

### Canonical evidence

Append-only or correction-preserving records:

- imported source records
- conversations and ordered messages
- tool calls and results
- memory writes
- session transitions
- delegation outcomes
- artifacts
- explicit user corrections and deletions

### Knowledge model

Revisable understanding derived from evidence:

- canonical identities
- assertions and supporting/contradicting evidence
- projects
- tasks
- decisions
- procedures
- outcomes
- improvement proposals

### Retrieval projections

Disposable, rebuildable optimization structures:

- embeddings
- lexical indexes
- chunks
- active context snapshots
- query caches
- retrieval feedback

## Hermes bootstrap import

The initial importer must support dry-run, resume, idempotency, and rollback by import run.

Import order:

1. Hermes `USER.md`
2. Hermes `MEMORY.md`
3. project/context files
4. session metadata, summaries, and transcripts
5. skills as procedural knowledge
6. cron jobs as structured proactive commitments
7. selected external memory provider export

Every record retains source system, source type, source identifier, original hash, import run, authority, speaker, timestamps, and canonical user scope.

## Provider semantics

### Mem0

Import atomic memories with provider IDs, user/agent IDs, dates, metadata, and deletion markers. Reuse the same configured canonical user ID across Hermes gateways.

### Honcho

Import observations and user-model conclusions separately. Honcho deductions are `provider_inference`, never `user_confirmed` facts.

### Other providers

Each adapter declares supported semantics: facts, episodes, documents, user model, temporal validity, relationships, summaries, provenance, and deletion markers.

## Hermes provider lifecycle

The future `OpenBrainMemoryProvider` implements:

- `initialize`: load config, resolve identity, validate service, establish session, start durable queues.
- `prefetch`: return a small cached context packet.
- `queue_prefetch`: prepare likely next-turn context in the background.
- `sync_turn`: enqueue ordered user/assistant/tool messages using an idempotency key.
- `on_memory_write`: mirror built-in `USER.md` and `MEMORY.md` mutations as authoritative evidence.
- `on_session_switch`: preserve reset, resume, branch, compression, and rewind lineage.
- `on_pre_compress`: preserve decisions, unresolved tasks, corrections, failures, artifacts, and commitments.
- `on_delegation`: record task/result pairs as attempts and outcomes.
- `on_session_end`: finalize session summary, open work, decisions, reusable lessons, and candidate improvements.
- `shutdown`: durably spool or flush pending writes without blocking indefinitely.

## Context delivery contract

Normal turns receive a compact packet, not raw memory fragments:

```json
{
  "packet_id": "ctx_...",
  "revision": 1,
  "scope": {
    "user_id": "...",
    "workspace_id": "...",
    "project_id": "...",
    "task_id": "...",
    "session_id": "..."
  },
  "current_state": {},
  "confirmed_decisions": [],
  "constraints": [],
  "relevant_lessons": [],
  "warnings": [],
  "suggested_actions": [],
  "provenance": []
}
```

Trust labels must distinguish `USER_CONFIRMED`, `TOOL_OBSERVED`, `CURATED_MEMORY`, `PROVIDER_INFERENCE`, `OPENBRAIN_INFERENCE`, `STALE`, and `CONTRADICTED`.

## Retrieval strategy

1. Resolve user, workspace, project, task, session, and platform scope.
2. Fetch exact active state through indexed relational queries.
3. Run hybrid semantic + lexical + entity + temporal retrieval only where necessary.
4. Rerank by relevance, authority, freshness, usefulness, contradiction state, and diversity.
5. Pack under a strict token and item budget.
6. Let Hermes drill into evidence through tools for deep historical work.

Initial latency objectives:

- cached context: under 10 ms
- active state lookup: under 20 ms
- normal context packet p95: under 200 ms
- hard provider timeout: 750 ms
- turn write enqueue acknowledgement: under 20 ms

Hermes must continue when Open Brain is unavailable, using built-in memory and the last valid snapshot while writes spool locally.

## Memory lifecycle

Knowledge states:

- candidate
- active
- confirmed
- superseded
- contradicted
- dormant
- archived
- deleted

Pruning means, in order:

1. consolidate duplicate evidence into canonical assertions
2. demote stale or low-value items from normal retrieval
3. archive raw history and large artifacts
4. tombstone before physical deletion
5. delete only by explicit request, retention policy, exact duplication, sensitivity expiry, or corruption

Stable user preferences and explicit decisions decay very slowly or never. Project and session state decay quickly unless refreshed.

## Self-improvement loop

```text
Hermes performs work
  -> Open Brain records trajectory and outcome
  -> compares with previous attempts
  -> extracts a reusable lesson
  -> proposes a context rule, checklist, procedure, skill patch, or guardrail
  -> Hermes tests or requests approval
  -> outcome returns to Open Brain
  -> proposal is promoted, revised, or rejected
```

Open Brain may automatically improve ranking and context summaries. Skill modifications, automations, permissions, safety rules, and destructive changes require review or explicit approval.

## First production slice

The first implementation milestone is deliberately narrow:

1. additive v2 schema for identities, events, sessions, assertions/evidence, projects, tasks, decisions, outcomes, import ledger, and context revisions
2. idempotent event ingestion query layer
3. structured context API over active project/task/decision state
4. Hermes bootstrap importer interfaces and import ledger
5. lifecycle states without physical deletion
6. tests for schema contracts, idempotency, lineage, and trust/provenance preservation

The Hermes plugin itself follows after these service contracts are stable.
