from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUERIES = (ROOT / "src" / "db" / "context_queries.py").read_text()
MIGRATION = (ROOT / "src" / "db" / "migrations" / "011_context_retrieval_indexes.sql").read_text()


def test_scope_revisions_are_batched():
    section = QUERIES.split("def get_scope_revisions", 1)[1].split("def increment_scope_revision", 1)[0]
    assert "UNNEST(%s::text[], %s::uuid[])" in section
    assert section.count("cursor.execute(") == 2
    assert "for scope_type, scope_id in scopes:" not in section


def test_current_context_queries_do_not_use_boolean_or_filters():
    section = QUERIES.split("def _fetch_project_context", 1)[1].split("def _assertion_id", 1)[0]
    assert "(%s OR" not in section
    assert "status NOT IN ('completed', 'cancelled', 'archived')" in section
    assert "status = 'active'" in section
    assert "status IN ('active', 'confirmed')" in section


def test_indexes_match_context_ordering_and_current_filters():
    assert "idx_task_context_current" in MIGRATION
    assert "priority DESC, updated_at DESC" in MIGRATION
    assert "idx_decision_context_current" in MIGRATION
    assert "WHERE status = 'active'" in MIGRATION
    assert "idx_assertion_context_current" in MIGRATION
    assert "importance DESC" in MIGRATION
    assert "last_confirmed_at DESC NULLS LAST" in MIGRATION
    assert "WHERE status IN ('active', 'confirmed')" in MIGRATION


def test_history_remains_queryable():
    assert "idx_task_context_history" in MIGRATION
    assert "idx_decision_context_history" in MIGRATION
    assert "idx_assertion_context_history" in MIGRATION
    assert "if include_history:" in QUERIES
