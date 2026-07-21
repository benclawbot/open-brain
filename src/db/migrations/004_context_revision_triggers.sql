-- Automatically invalidate cached context whenever canonical scoped state changes.

CREATE OR REPLACE FUNCTION openbrain_bump_context_revision(p_scope_type TEXT, p_scope_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_scope_id IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO context_revision (scope_type, scope_id, revision)
    VALUES (p_scope_type, p_scope_id, 1)
    ON CONFLICT (scope_type, scope_id) DO UPDATE SET
        revision = context_revision.revision + 1,
        updated_at = NOW();
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_bump_project_context(p_project_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    owner_id UUID;
BEGIN
    IF p_project_id IS NULL THEN
        RETURN;
    END IF;

    PERFORM openbrain_bump_context_revision('project', p_project_id);
    SELECT owner_identity_id INTO owner_id FROM project WHERE id = p_project_id;
    PERFORM openbrain_bump_context_revision('user', owner_id);
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_bump_task_context(p_task_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    parent_project_id UUID;
BEGIN
    IF p_task_id IS NULL THEN
        RETURN;
    END IF;

    PERFORM openbrain_bump_context_revision('task', p_task_id);
    SELECT project_id INTO parent_project_id FROM task WHERE id = p_task_id;
    PERFORM openbrain_bump_project_context(parent_project_id);
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_project_context_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM openbrain_bump_context_revision('project', OLD.id);
        PERFORM openbrain_bump_context_revision('user', OLD.owner_identity_id);
        RETURN OLD;
    END IF;

    PERFORM openbrain_bump_context_revision('project', NEW.id);
    PERFORM openbrain_bump_context_revision('user', NEW.owner_identity_id);
    IF TG_OP = 'UPDATE' AND OLD.owner_identity_id IS DISTINCT FROM NEW.owner_identity_id THEN
        PERFORM openbrain_bump_context_revision('user', OLD.owner_identity_id);
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_task_context_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM openbrain_bump_context_revision('task', OLD.id);
        PERFORM openbrain_bump_project_context(OLD.project_id);
        RETURN OLD;
    END IF;

    PERFORM openbrain_bump_context_revision('task', NEW.id);
    PERFORM openbrain_bump_project_context(NEW.project_id);
    IF TG_OP = 'UPDATE' AND OLD.project_id IS DISTINCT FROM NEW.project_id THEN
        PERFORM openbrain_bump_project_context(OLD.project_id);
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_project_task_context_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM openbrain_bump_context_revision('task', OLD.task_id);
        PERFORM openbrain_bump_project_context(OLD.project_id);
        RETURN OLD;
    END IF;

    PERFORM openbrain_bump_context_revision('task', NEW.task_id);
    PERFORM openbrain_bump_project_context(NEW.project_id);
    IF TG_OP = 'UPDATE' THEN
        IF OLD.task_id IS DISTINCT FROM NEW.task_id THEN
            PERFORM openbrain_bump_context_revision('task', OLD.task_id);
        END IF;
        IF OLD.project_id IS DISTINCT FROM NEW.project_id THEN
            PERFORM openbrain_bump_project_context(OLD.project_id);
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION openbrain_assertion_context_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    row_subject_type TEXT;
    row_subject_id UUID;
BEGIN
    row_subject_type := CASE WHEN TG_OP = 'DELETE' THEN OLD.subject_type ELSE NEW.subject_type END;
    row_subject_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.subject_id ELSE NEW.subject_id END;

    IF row_subject_type IN ('user', 'project', 'task') THEN
        PERFORM openbrain_bump_context_revision(row_subject_type, row_subject_id);
        IF row_subject_type = 'task' THEN
            PERFORM openbrain_bump_task_context(row_subject_id);
        ELSIF row_subject_type = 'project' THEN
            PERFORM openbrain_bump_project_context(row_subject_id);
        END IF;
    END IF;

    IF TG_OP = 'UPDATE'
       AND (OLD.subject_type, OLD.subject_id) IS DISTINCT FROM (NEW.subject_type, NEW.subject_id)
       AND OLD.subject_type IN ('user', 'project', 'task') THEN
        PERFORM openbrain_bump_context_revision(OLD.subject_type, OLD.subject_id);
        IF OLD.subject_type = 'task' THEN
            PERFORM openbrain_bump_task_context(OLD.subject_id);
        ELSIF OLD.subject_type = 'project' THEN
            PERFORM openbrain_bump_project_context(OLD.subject_id);
        END IF;
    END IF;

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

DROP TRIGGER IF EXISTS trg_project_context_revision ON project;
CREATE TRIGGER trg_project_context_revision
AFTER INSERT OR UPDATE OR DELETE ON project
FOR EACH ROW EXECUTE FUNCTION openbrain_project_context_trigger();

DROP TRIGGER IF EXISTS trg_task_context_revision ON task;
CREATE TRIGGER trg_task_context_revision
AFTER INSERT OR UPDATE OR DELETE ON task
FOR EACH ROW EXECUTE FUNCTION openbrain_task_context_trigger();

DROP TRIGGER IF EXISTS trg_decision_context_revision ON decision;
CREATE TRIGGER trg_decision_context_revision
AFTER INSERT OR UPDATE OR DELETE ON decision
FOR EACH ROW EXECUTE FUNCTION openbrain_project_task_context_trigger();

DROP TRIGGER IF EXISTS trg_outcome_context_revision ON outcome;
CREATE TRIGGER trg_outcome_context_revision
AFTER INSERT OR UPDATE OR DELETE ON outcome
FOR EACH ROW EXECUTE FUNCTION openbrain_project_task_context_trigger();

DROP TRIGGER IF EXISTS trg_assertion_context_revision ON assertion;
CREATE TRIGGER trg_assertion_context_revision
AFTER INSERT OR UPDATE OR DELETE ON assertion
FOR EACH ROW EXECUTE FUNCTION openbrain_assertion_context_trigger();
