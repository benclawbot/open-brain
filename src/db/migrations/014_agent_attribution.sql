ALTER TABLE memory
    ADD COLUMN IF NOT EXISTS captured_by TEXT;

CREATE INDEX IF NOT EXISTS idx_memory_captured_by
    ON memory (captured_by);
