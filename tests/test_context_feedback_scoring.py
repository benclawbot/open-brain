from __future__ import annotations

from uuid import uuid4

from db.connection import get_db_cursor
from db.context_queries import save_context_feedback


def _counters(assertion_id: str) -> tuple[int, int, int]:
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT access_count, useful_count, harmful_count FROM assertion WHERE id = %s::uuid",
            (assertion_id,),
        )
        row = cursor.fetchone()
        return int(row["access_count"]), int(row["useful_count"]), int(row["harmful_count"])


def _feedback(packet_id: str, assertion_id: str, disposition: str) -> dict:
    return {
        "packet_id": packet_id,
        "items": [
            {
                "context_item_id": assertion_id,
                "disposition": disposition,
                "note": f"marked {disposition}",
            }
        ],
        "missing": [],
        "outcome": "completed",
    }


def test_feedback_updates_assertion_counters_once_per_packet_item():
    assertion_id = str(uuid4())
    used_packet = str(uuid4())
    irrelevant_packet = str(uuid4())
    incorrect_packet = str(uuid4())

    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO assertion (id, subject_type, predicate, value, status)
                VALUES (%s::uuid, 'user', 'preferred_tool', %s::jsonb, 'active')
                """,
                (assertion_id, '"Open Brain"'),
            )

        first = save_context_feedback(used_packet, _feedback(used_packet, assertion_id, "used"))
        duplicate = save_context_feedback(used_packet, _feedback(used_packet, assertion_id, "used"))
        irrelevant = save_context_feedback(
            irrelevant_packet,
            _feedback(irrelevant_packet, assertion_id, "irrelevant"),
        )
        incorrect = save_context_feedback(
            incorrect_packet,
            _feedback(incorrect_packet, assertion_id, "incorrect"),
        )

        assert first == {"applied": 1, "duplicates": 0, "assertions_updated": 1}
        assert duplicate == {"applied": 0, "duplicates": 1, "assertions_updated": 0}
        assert irrelevant["assertions_updated"] == 1
        assert incorrect["assertions_updated"] == 1
        assert _counters(assertion_id) == (3, 1, 1)

        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT disposition FROM context_feedback_application WHERE assertion_id = %s::uuid ORDER BY disposition",
                (assertion_id,),
            )
            assert [row["disposition"] for row in cursor.fetchall()] == [
                "incorrect",
                "irrelevant",
                "used",
            ]
    finally:
        with get_db_cursor() as cursor:
            cursor.execute(
                "DELETE FROM context_feedback_application WHERE assertion_id = %s::uuid",
                (assertion_id,),
            )
            cursor.execute(
                "DELETE FROM event WHERE idempotency_key = ANY(%s)",
                ([
                    f"context-feedback:{used_packet}",
                    f"context-feedback:{irrelevant_packet}",
                    f"context-feedback:{incorrect_packet}",
                ],),
            )
            cursor.execute("DELETE FROM assertion WHERE id = %s::uuid", (assertion_id,))
