-- Query-path indexes for low-latency context packet assembly.

CREATE INDEX IF NOT EXISTS idx_context_revision_scope_lookup
    ON context_revision (scope_type, scope_id, revision);

CREATE INDEX IF NOT EXISTS idx_task_context_current
    ON task (project_id, priority DESC, updated_at DESC)
    WHERE status NOT IN ('completed', 'cancelled', 'archived');

CREATE INDEX IF NOT EXISTS idx_task_context_history
    ON task (project_id, priority DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_decision_context_current
    ON decision (project_id, decided_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_decision_context_history
    ON decision (project_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_outcome_context_recent
    ON outcome (project_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_assertion_context_current
    ON assertion (
        subject_id,
        importance DESC,
        last_confirmed_at DESC NULLS LAST,
        last_observed_at DESC
    )
    WHERE status IN ('active', 'confirmed');

CREATE INDEX IF NOT EXISTS idx_assertion_context_history
    ON assertion (
        subject_id,
        importance DESC,
        last_confirmed_at DESC NULLS LAST,
        last_observed_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_context_feedback_assertion
    ON context_feedback_application (assertion_id)
    WHERE assertion_id IS NOT NULL;
