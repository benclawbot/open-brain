from __future__ import annotations

from uuid import uuid4

from db.connection import get_db_cursor


def _revision(scope_type: str, scope_id) -> int:
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT revision FROM context_revision WHERE scope_type = %s AND scope_id = %s",
            (scope_type, scope_id),
        )
        row = cursor.fetchone()
        return int(row["revision"]) if row else 0


def test_canonical_mutations_bump_task_project_and_user_context():
    identity_id = uuid4()
    project_id = uuid4()
    task_id = uuid4()
    decision_id = uuid4()
    assertion_id = uuid4()

    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO identity (id, kind, canonical_key) VALUES (%s, 'user', %s)",
                (identity_id, f"revision-user-{identity_id}"),
            )
            cursor.execute(
                "INSERT INTO project (id, owner_identity_id, canonical_key, name) VALUES (%s, %s, %s, 'Revision test')",
                (project_id, identity_id, f"revision-project-{project_id}"),
            )
            cursor.execute(
                "INSERT INTO task (id, project_id, canonical_key, title) VALUES (%s, %s, %s, 'Initial task')",
                (task_id, project_id, f"revision-task-{task_id}"),
            )

        initial_task = _revision("task", task_id)
        initial_project = _revision("project", project_id)
        initial_user = _revision("user", identity_id)
        assert initial_task >= 1
        assert initial_project >= 1
        assert initial_user >= 1

        with get_db_cursor() as cursor:
            cursor.execute("UPDATE task SET next_action = 'Run verification' WHERE id = %s", (task_id,))

        assert _revision("task", task_id) > initial_task
        assert _revision("project", project_id) > initial_project
        assert _revision("user", identity_id) > initial_user

        before_decision_task = _revision("task", task_id)
        before_decision_project = _revision("project", project_id)
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO decision (id, project_id, task_id, statement) VALUES (%s, %s, %s, 'Use revision triggers')",
                (decision_id, project_id, task_id),
            )

        assert _revision("task", task_id) > before_decision_task
        assert _revision("project", project_id) > before_decision_project

        before_assertion_task = _revision("task", task_id)
        before_assertion_project = _revision("project", project_id)
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO assertion (id, subject_type, subject_id, predicate, value)
                VALUES (%s, 'task', %s, 'next_action', %s::jsonb)
                """,
                (assertion_id, task_id, '"Run verification"'),
            )

        assert _revision("task", task_id) > before_assertion_task
        assert _revision("project", project_id) > before_assertion_project
    finally:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM assertion WHERE id = %s", (assertion_id,))
            cursor.execute("DELETE FROM decision WHERE id = %s", (decision_id,))
            cursor.execute("DELETE FROM task WHERE id = %s", (task_id,))
            cursor.execute("DELETE FROM project WHERE id = %s", (project_id,))
            cursor.execute("DELETE FROM identity WHERE id = %s", (identity_id,))
