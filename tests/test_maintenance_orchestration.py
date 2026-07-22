from unittest.mock import patch

from src.maintenance.orchestrator import MaintenanceOptions, run_maintenance


def test_dry_run_does_not_generate_or_delete():
    with (
        patch("src.maintenance.orchestrator.generate_consolidation_proposals") as consolidate,
        patch("src.maintenance.orchestrator.generate_pruning_proposals") as prune,
        patch("src.maintenance.orchestrator.cleanup_context_cache") as cleanup,
        patch("src.maintenance.orchestrator.context_cache_stats", return_value={"rows": 3}),
        patch("src.maintenance.orchestrator._tombstone_retention_report", return_value={"active": 1, "past_retention": 0}),
    ):
        report = run_maintenance(MaintenanceOptions(dry_run=True))
    consolidate.assert_not_called()
    prune.assert_not_called()
    cleanup.assert_not_called()
    assert report["status"] == "completed"
    assert report["summary"]["failed"] == 0


def test_failure_isolation_runs_later_steps():
    with (
        patch("src.maintenance.orchestrator.generate_consolidation_proposals", side_effect=RuntimeError("boom")),
        patch("src.maintenance.orchestrator.generate_pruning_proposals", return_value=[]),
        patch("src.maintenance.orchestrator.cleanup_context_cache", return_value={"expired": 0, "overflow": 0}),
        patch("src.maintenance.orchestrator.context_cache_stats", return_value={"rows": 0}),
        patch("src.maintenance.orchestrator._tombstone_retention_report", return_value={"active": 0, "past_retention": 0}),
    ):
        report = run_maintenance(MaintenanceOptions(dry_run=False))
    assert report["status"] == "completed_with_failures"
    assert report["steps"][0]["status"] == "failed"
    assert report["steps"][1]["status"] == "succeeded"
    assert report["steps"][2]["status"] == "succeeded"


def test_limits_are_validated_before_work_starts():
    try:
        run_maintenance(MaintenanceOptions(proposal_limit=0))
    except ValueError as exc:
        assert "proposal_limit" in str(exc)
    else:
        raise AssertionError("invalid limits must fail")
