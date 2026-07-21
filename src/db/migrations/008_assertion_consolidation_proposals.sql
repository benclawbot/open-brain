CREATE TABLE IF NOT EXISTS assertion_consolidation_proposal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    survivor_id UUID NOT NULL REFERENCES assertion(id) ON DELETE CASCADE,
    redundant_id UUID NOT NULL REFERENCES assertion(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('duplicate', 'supersede')),
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1),
    reasons JSONB NOT NULL DEFAULT '[]',
    survivor_snapshot JSONB NOT NULL,
    redundant_snapshot JSONB NOT NULL,
    policy_version TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'accepted', 'rejected', 'superseded')),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (survivor_id, redundant_id, fingerprint),
    CHECK (survivor_id <> redundant_id)
);

CREATE INDEX IF NOT EXISTS idx_assertion_consolidation_pending
    ON assertion_consolidation_proposal (state, score DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_assertion_consolidation_survivor
    ON assertion_consolidation_proposal (survivor_id, state);
CREATE INDEX IF NOT EXISTS idx_assertion_consolidation_redundant
    ON assertion_consolidation_proposal (redundant_id, state);
