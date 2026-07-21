from uuid import UUID

from context.cache import cache_key, hydrate_packet, packet_template, request_fingerprint
from context.models import ContextItem, ContextKind, ContextPacket, ContextRequest, TrustLabel


def request(**overrides):
    values = {
        "user_identity_id": UUID("00000000-0000-0000-0000-000000000001"),
        "project_id": UUID("00000000-0000-0000-0000-000000000002"),
        "task_id": None,
        "max_items": 20,
        "token_budget": 1600,
        "include_history": False,
    }
    values.update(overrides)
    return ContextRequest(**values)


def test_cache_key_is_stable_for_equivalent_revision_maps():
    revisions_a = {"project:p": 3, "user:u": 7}
    revisions_b = {"user:u": 7, "project:p": 3}
    assert cache_key(request(), revisions_a) == cache_key(request(), revisions_b)


def test_cache_key_changes_for_request_or_revision_changes():
    base = cache_key(request(), {"project:p": 3})
    assert base != cache_key(request(max_items=21), {"project:p": 3})
    assert base != cache_key(request(), {"project:p": 4})
    assert base != cache_key(request(include_history=True), {"project:p": 3})


def test_request_fingerprint_contains_only_retrieval_inputs():
    fingerprint = request_fingerprint(request())
    assert fingerprint == {
        "user_identity_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "00000000-0000-0000-0000-000000000002",
        "task_id": None,
        "max_items": 20,
        "token_budget": 1600,
        "include_history": False,
    }


def test_cached_template_gets_fresh_packet_identity():
    packet = ContextPacket(
        packet_id=UUID("00000000-0000-0000-0000-000000000010"),
        scope_revisions={"project:p": 2},
        items=[ContextItem(
            id="assertion-1",
            kind=ContextKind.ASSERTION,
            text="language: Python",
            trust=TrustLabel.USER_CONFIRMED,
            importance=0.8,
        )],
        estimated_tokens=12,
        truncated=False,
    )
    template = packet_template(packet)
    assert "packet_id" not in template
    assert "generated_at" not in template

    first = hydrate_packet(template)
    second = hydrate_packet(template)
    assert first.packet_id != packet.packet_id
    assert first.packet_id != second.packet_id
    assert first.items == second.items == packet.items
    assert first.scope_revisions == packet.scope_revisions
