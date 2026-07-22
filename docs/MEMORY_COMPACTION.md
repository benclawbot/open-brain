# Memory compaction

Open Brain can create durable rollups from older repetitive continuity events without deleting or rewriting the original events.

## Run a compaction

```http
POST /v1/compaction/run
Content-Type: application/json

{
  "scope_type": "project",
  "scope_id": "00000000-0000-0000-0000-000000000000",
  "older_than_days": 14,
  "minimum_events": 3,
  "limit": 500,
  "dry_run": true
}
```

Set `dry_run` to `false` to persist candidates.

## Safety properties

- Every rollup has immutable links to all source event IDs.
- Every source event receives a deterministic content fingerprint.
- The complete source set receives a policy-versioned fingerprint.
- Identical reruns are idempotent.
- A changed source set creates a new active rollup and supersedes the previous one.
- Raw events are never deleted, edited, or hidden from direct provenance inspection.
- Context retrieval emits only the active rollup, not the rollup beside all of its raw sources, preventing duplicate evidence from consuming the retrieval budget.
- Derived rollups are explicitly labelled `curated_memory` and carry source count, source fingerprint, and policy version metadata.

The current summarizer is deterministic and extractive. It intentionally avoids an external model dependency so regeneration remains reproducible and auditable.
