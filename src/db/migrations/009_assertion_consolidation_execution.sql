ALTER TABLE assertion_consolidation_proposal ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ;
ALTER TABLE assertion_consolidation_proposal ADD COLUMN IF NOT EXISTS applied_by TEXT;
ALTER TABLE assertion_consolidation_proposal ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ;
ALTER TABLE assertion_consolidation_proposal ADD COLUMN IF NOT EXISTS reversed_by TEXT;

CREATE TABLE IF NOT EXISTS assertion_consolidation_execution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL UNIQUE REFERENCES assertion_consolidation_proposal(id),
    survivor_id UUID NOT NULL REFERENCES assertion(id),
    redundant_id UUID NOT NULL REFERENCES assertion(id),
    action TEXT NOT NULL,
    previous_redundant_status TEXT NOT NULL,
    previous_superseded_by UUID REFERENCES assertion(id),
    survivor_snapshot JSONB NOT NULL,
    redundant_snapshot JSONB NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reversed_at TIMESTAMPTZ,
    reversed_by TEXT,
    reversal_note TEXT
);