-- Revision-keyed cache for compact context packet templates.

CREATE TABLE IF NOT EXISTS context_packet_cache (
    cache_key TEXT PRIMARY KEY,
    request_fingerprint JSONB NOT NULL,
    scope_revisions JSONB NOT NULL,
    packet_template JSONB NOT NULL,
    item_count INTEGER NOT NULL CHECK (item_count >= 0),
    estimated_tokens INTEGER NOT NULL CHECK (estimated_tokens >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hit_count BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_context_packet_cache_expiry
    ON context_packet_cache (expires_at);

CREATE INDEX IF NOT EXISTS idx_context_packet_cache_activity
    ON context_packet_cache (last_accessed_at DESC);
