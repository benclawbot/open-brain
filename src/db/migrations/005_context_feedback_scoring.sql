-- Persist one application decision per context packet item so feedback cannot double-count.

CREATE TABLE IF NOT EXISTS context_feedback_application (
    packet_id UUID NOT NULL,
    context_item_id TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('used', 'irrelevant', 'incorrect', 'missing')),
    assertion_id UUID REFERENCES assertion(id) ON DELETE SET NULL,
    note TEXT,
    outcome TEXT,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (packet_id, context_item_id)
);

CREATE INDEX IF NOT EXISTS idx_context_feedback_assertion
    ON context_feedback_application (assertion_id, applied_at DESC)
    WHERE assertion_id IS NOT NULL;
