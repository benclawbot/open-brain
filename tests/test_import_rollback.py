from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.imports import ImportRollbackRequest, ImportRollbackResponse


def test_rollback_request_requires_actor_and_reason():
    with pytest.raises(ValidationError):
        ImportRollbackRequest(actor="", reason="cleanup")
    with pytest.raises(ValidationError):
        ImportRollbackRequest(actor="operator", reason="")


def test_rollback_response_reports_tombstoned_record_count():
    response = ImportRollbackResponse(
        id=uuid4(),
        status="rolled_back",
        rolled_back_by="operator",
        rollback_reason="wrong source export",
        rolled_back_records=4,
    )
    assert response.status == "rolled_back"
    assert response.rolled_back_records == 4


def test_rollback_migration_is_packaged():
    from importlib.resources import files

    migration = files("src.db.migrations").joinpath("003_import_rollback.sql")
    content = migration.read_text(encoding="utf-8")
    assert "rolled_back_at" in content
    assert "tombstone" in content
