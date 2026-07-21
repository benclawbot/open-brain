ALTER TABLE assertion_lifecycle_proposal
    ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS applied_by TEXT,
    ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reversed_by TEXT;

CREATE TABLE IF NOT EXISTS assertion_lifecycle_execution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL UNIQUE REFERENCES assertion_lifecycle_proposal(id) ON DELETE CASCADE,
    assertion_id UUID NOT NULL REFERENCES assertion(id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    applied_status TEXT NOT NULL,
    assertion_snapshot JSONB NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reversed_at TIMESTAMPTZ,
    reversed_by TEXT,
    reversal_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_assertion_lifecycle_execution_assertion
    ON assertion_lifecycle_execution (assertion_id, applied_at DESC);
