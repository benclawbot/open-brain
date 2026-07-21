-- Reversible staged-import metadata. Rollback is an audit transition, never deletion.

ALTER TABLE import_run
    ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rolled_back_by TEXT,
    ADD COLUMN IF NOT EXISTS rollback_reason TEXT;

ALTER TABLE import_record
    ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rolled_back_by TEXT,
    ADD COLUMN IF NOT EXISTS rollback_reason TEXT,
    ADD COLUMN IF NOT EXISTS tombstone JSONB;

CREATE INDEX IF NOT EXISTS idx_import_run_rollback
    ON import_run (rolled_back_at DESC)
    WHERE rolled_back_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_import_record_active_stage
    ON import_record (import_run_id, created_at)
    WHERE operation = 'stage' AND rolled_back_at IS NULL;
