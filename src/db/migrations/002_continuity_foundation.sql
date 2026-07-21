-- Open Brain continuity foundation (additive v2 schema)
-- Safe to apply alongside the existing memory table.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS identity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind TEXT NOT NULL CHECK (kind IN ('user', 'agent', 'workspace', 'platform_user')),
    canonical_key TEXT NOT NULL,
    display_name TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (kind, canonical_key)
);

CREATE TABLE IF NOT EXISTS identity_link (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_identity_id UUID NOT NULL REFERENCES identity(id) ON DELETE CASCADE,
    source_system TEXT NOT NULL,
    external_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system, external_type, external_id)
);

CREATE TABLE IF NOT EXISTS project (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_identity_id UUID REFERENCES identity(id),
    canonical_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    revision BIGINT NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES project(id) ON DELETE SET NULL,
    parent_task_id UUID REFERENCES task(id) ON DELETE SET NULL,
    canonical_key TEXT,
    title TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER NOT NULL DEFAULT 0,
    current_plan JSONB NOT NULL DEFAULT '[]',
    next_action TEXT,
    blockers JSONB NOT NULL DEFAULT '[]',
    revision BIGINT NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE (project_id, canonical_key)
);

CREATE TABLE IF NOT EXISTS session (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_session_id TEXT NOT NULL,
    source_system TEXT NOT NULL DEFAULT 'hermes',
    user_identity_id UUID REFERENCES identity(id),
    agent_identity_id UUID REFERENCES identity(id),
    workspace_identity_id UUID REFERENCES identity(id),
    project_id UUID REFERENCES project(id),
    task_id UUID REFERENCES task(id),
    parent_session_id UUID REFERENCES session(id),
    lineage_reason TEXT CHECK (lineage_reason IN ('new', 'reset', 'resume', 'branch', 'compression', 'rewind')),
    platform TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    UNIQUE (source_system, external_session_id)
);

CREATE TABLE IF NOT EXISTS event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    user_identity_id UUID REFERENCES identity(id),
    agent_identity_id UUID REFERENCES identity(id),
    workspace_identity_id UUID REFERENCES identity(id),
    session_id UUID REFERENCES session(id),
    project_id UUID REFERENCES project(id),
    task_id UUID REFERENCES task(id),
    causation_id UUID REFERENCES event(id),
    correlation_id UUID,
    authority TEXT NOT NULL DEFAULT 'unknown',
    sensitivity TEXT NOT NULL DEFAULT 'normal',
    retention_policy TEXT NOT NULL DEFAULT 'default',
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS assertion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type TEXT NOT NULL,
    subject_id UUID,
    predicate TEXT NOT NULL,
    value JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (
        status IN ('candidate', 'active', 'confirmed', 'superseded', 'contradicted', 'dormant', 'archived', 'deleted')
    ),
    authority DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (authority >= 0 AND authority <= 1),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    temporal_class TEXT NOT NULL DEFAULT 'slow-changing' CHECK (
        temporal_class IN ('stable', 'slow-changing', 'project-state', 'session-state', 'ephemeral')
    ),
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    first_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_confirmed_at TIMESTAMPTZ,
    last_accessed_at TIMESTAMPTZ,
    access_count BIGINT NOT NULL DEFAULT 0,
    useful_count BIGINT NOT NULL DEFAULT 0,
    harmful_count BIGINT NOT NULL DEFAULT 0,
    superseded_by UUID REFERENCES assertion(id),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS assertion_evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assertion_id UUID NOT NULL REFERENCES assertion(id) ON DELETE CASCADE,
    event_id UUID REFERENCES event(id) ON DELETE SET NULL,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    evidence_type TEXT NOT NULL,
    stance TEXT NOT NULL CHECK (stance IN ('supports', 'contradicts', 'qualifies', 'supersedes')),
    authority DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    excerpt TEXT,
    observed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES project(id) ON DELETE SET NULL,
    task_id UUID REFERENCES task(id) ON DELETE SET NULL,
    assertion_id UUID REFERENCES assertion(id) ON DELETE SET NULL,
    statement TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_by UUID REFERENCES decision(id),
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS outcome (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES project(id) ON DELETE SET NULL,
    task_id UUID REFERENCES task(id) ON DELETE SET NULL,
    session_id UUID REFERENCES session(id) ON DELETE SET NULL,
    event_id UUID REFERENCES event(id) ON DELETE SET NULL,
    objective TEXT,
    result TEXT,
    success BOOLEAN,
    validation JSONB NOT NULL DEFAULT '{}',
    lessons JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system TEXT NOT NULL,
    source_instance TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    cursor JSONB,
    config JSONB NOT NULL DEFAULT '{}',
    records_seen BIGINT NOT NULL DEFAULT 0,
    records_imported BIGINT NOT NULL DEFAULT 0,
    records_merged BIGINT NOT NULL DEFAULT 0,
    records_rejected BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error TEXT
);

CREATE TABLE IF NOT EXISTS import_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    import_run_id UUID NOT NULL REFERENCES import_run(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    external_hash TEXT NOT NULL,
    object_type TEXT,
    object_id UUID,
    operation TEXT NOT NULL,
    result TEXT NOT NULL,
    error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (import_run_id, external_id, external_hash)
);

CREATE TABLE IF NOT EXISTS context_revision (
    scope_type TEXT NOT NULL,
    scope_id UUID NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope_type, scope_id)
);

CREATE INDEX IF NOT EXISTS idx_event_scope_recent
    ON event (user_identity_id, project_id, task_id, occurred_at DESC)
    WHERE archived_at IS NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_session_recent
    ON event (session_id, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_type_recent
    ON event (event_type, occurred_at DESC)
    WHERE archived_at IS NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_payload_gin ON event USING GIN (payload);

CREATE INDEX IF NOT EXISTS idx_assertion_active_subject
    ON assertion (subject_type, subject_id, predicate)
    WHERE status IN ('active', 'confirmed');
CREATE INDEX IF NOT EXISTS idx_assertion_current
    ON assertion (status, temporal_class, last_confirmed_at DESC, importance DESC)
    WHERE status IN ('active', 'confirmed');
CREATE INDEX IF NOT EXISTS idx_assertion_value_gin ON assertion USING GIN (value);

CREATE INDEX IF NOT EXISTS idx_task_active_project
    ON task (project_id, priority DESC, updated_at DESC)
    WHERE status NOT IN ('completed', 'cancelled', 'archived');
CREATE INDEX IF NOT EXISTS idx_decision_active_project
    ON decision (project_id, decided_at DESC)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_import_record_external
    ON import_record (external_id, external_hash);
