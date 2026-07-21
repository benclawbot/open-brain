# Assertion lifecycle review queue

Open Brain evaluates assertion quality without silently rewriting canonical memory.

## Generate proposals

```http
POST /v1/lifecycle/proposals/generate
Content-Type: application/json

{"limit": 250, "minimum_score": 0.25}
```

The evaluator considers harmful and useful retrieval feedback, supporting and contradicting evidence, authority, confidence, importance, access patterns, and temporal-class freshness. Healthy `keep` results are not stored.

Each stored proposal contains the proposed action, optional target status, score, reasons, policy version, and an immutable snapshot of the assertion signals used for evaluation. A SHA-256 fingerprint makes repeated generation idempotent until the assertion signals or policy result change.

## Review proposals

```http
GET /v1/lifecycle/proposals?state=pending&limit=100
```

Pending proposals are ordered by score and age so the highest-risk memory receives attention first.

```http
POST /v1/lifecycle/proposals/{proposal_id}/review
Content-Type: application/json

{
  "state": "accepted",
  "reviewed_by": "human-or-agent-identity",
  "note": "Validated against the upstream repository"
}
```

Review state may be `accepted` or `rejected`. This records the decision, reviewer, timestamp, and note. It does **not** mutate the assertion. Applying accepted proposals requires a future guarded execution workflow with stale-snapshot checks and reversal support.

## Safety properties

- Proposal generation is additive and idempotent.
- Canonical assertion status and value are never modified by these endpoints.
- Confirmed assertions remain protected by the lifecycle policy.
- The exact input snapshot and policy version remain available for audit.
- A proposal can be reviewed only while pending.
