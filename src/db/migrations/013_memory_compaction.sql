-- Durable, provenance-preserving event compaction.

CREATE TABLE IF NOT EXISTS memory_compaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scope_type TEXT NOT NULL CHECK (scope_type IN ('user','workspace','session','project','task')),
    scope_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    source_event_count INTEGER NOT NULL CHECK (source_event_count > 0),
    first_occurred_at TIMESTAMPTZ NOT NULL,
    last_occurred_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
    superseded_by UUID REFERENCES memory_compaction(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scope_type, scope_id, event_type, source_fingerprint)
);

CREATE TABLE IF NOT EXISTS memory_compaction_source (
    compaction_id UUID NOT NULL REFERENCES memory_compaction(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES event(id),
    event_fingerprint TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (compaction_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_compaction_scope_active
    ON memory_compaction (scope_type, scope_id, last_occurred_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_memory_compaction_source_event
    ON memory_compaction_source (event_id);
