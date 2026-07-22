DO $$
BEGIN
    IF to_regclass('public.memory') IS NOT NULL THEN
        ALTER TABLE memory
            ADD COLUMN IF NOT EXISTS captured_by TEXT;

        CREATE INDEX IF NOT EXISTS idx_memory_captured_by
            ON memory (captured_by);
    END IF;
END;
$$;
