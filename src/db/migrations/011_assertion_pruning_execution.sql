-- Execution metadata for reviewed assertion pruning proposals.

ALTER TABLE assertion_pruning_proposal
    ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS applied_by TEXT;
