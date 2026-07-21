CREATE TABLE IF NOT EXISTS assertion_lifecycle_proposal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assertion_id UUID NOT NULL REFERENCES assertion(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('keep', 'review', 'demote', 'archive')),
    target_status TEXT,
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1),
    reasons JSONB NOT NULL DEFAULT '[]',
    assertion_snapshot JSONB NOT NULL,
    policy_version TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'accepted', 'rejected', 'superseded')),
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_note TEXT,
    UNIQUE (assertion_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_assertion_lifecycle_pending
    ON assertion_lifecycle_proposal (state, score DESC, created_at DESC)
    WHERE state = 'pending';

CREATE INDEX IF NOT EXISTS idx_assertion_lifecycle_assertion
    ON assertion_lifecycle_proposal (assertion_id, created_at DESC);
