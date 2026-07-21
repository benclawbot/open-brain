"""Contract tests for canonical identity and Hermes session lineage."""

import pytest
from pydantic import ValidationError

from continuity.scopes import IdentityKind, IdentityRef, LineageReason, SessionOpen


def test_identity_normalizes_canonical_key():
    identity = IdentityRef(kind=IdentityKind.USER, canonical_key="  Ben  ")
    assert identity.canonical_key == "ben"


def test_external_identity_link_requires_complete_triple():
    with pytest.raises(ValidationError):
        IdentityRef(
            kind=IdentityKind.USER,
            canonical_key="ben",
            source_system="hermes",
            external_id="123",
        )


def test_complete_external_identity_link_is_valid():
    identity = IdentityRef(
        kind=IdentityKind.USER,
        canonical_key="ben",
        source_system="hermes",
        external_type="telegram_user",
        external_id="123",
    )
    assert identity.external_type == "telegram_user"


def test_branch_requires_parent_external_session():
    with pytest.raises(ValidationError):
        SessionOpen(
            external_session_id="child",
            lineage_reason=LineageReason.BRANCH,
        )


def test_reset_does_not_require_parent_session():
    request = SessionOpen(
        external_session_id="fresh",
        lineage_reason=LineageReason.RESET,
    )
    assert request.parent_external_session_id is None


def test_resume_with_parent_is_valid():
    request = SessionOpen(
        external_session_id="resumed",
        lineage_reason=LineageReason.RESUME,
        parent_external_session_id="previous",
    )
    assert request.parent_external_session_id == "previous"
