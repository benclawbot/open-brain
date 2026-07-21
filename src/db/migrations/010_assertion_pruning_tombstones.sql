-- Reversible assertion pruning with immutable tombstones.

CREATE TABLE IF NOT EXISTS assertion_pruning_proposal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assertion_id UUID NOT NULL REFERENCES assertion(id),
    reason TEXT NOT NULL CHECK (reason IN (
        'expired_ephemeral', 'stale_session_state', 'harmful_low_value',
        'superseded_old', 'contradicted_old'
    )),
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1),
    retention_days INTEGER NOT NULL CHECK (retention_days >= 1),
    assertion_snapshot JSONB NOT NULL,
    fingerprint TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (
        state IN ('pending', 'accepted', 'rejected', 'applied', 'reversed', 'stale')
    ),
    reviewed_by TEXT,
    review_note TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (assertion_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS assertion_tombstone (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL UNIQUE REFERENCES assertion_pruning_proposal(id),
    assertion_id UUID NOT NULL REFERENCES assertion(id),
    previous_status TEXT NOT NULL,
    assertion_snapshot JSONB NOT NULL,
    evidence_count BIGINT NOT NULL,
    reason TEXT NOT NULL,
    retention_until TIMESTAMPTZ NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reversed_by TEXT,
    reversed_at TIMESTAMPTZ,
    reversal_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_assertion_pruning_pending
    ON assertion_pruning_proposal (score DESC, created_at ASC)
    WHERE state = 'pending';

CREATE INDEX IF NOT EXISTS idx_assertion_tombstone_retention
    ON assertion_tombstone (retention_until)
    WHERE reversed_at IS NULL;
