from __future__ import annotations

from src.release.readiness import evaluate_release_readiness


def production_env(**overrides: str) -> dict[str, str]:
    values = {
        "OPENBRAIN_ENV": "production",
        "OPENBRAIN_AUTH_REQUIRED": "true",
        "OPENBRAIN_API_KEY": "a" * 32,
        "OPENBRAIN_CORS_ORIGINS": "https://brain.example.com",
        "OPENBRAIN_ATTEST_TLS": "true",
        "OPENBRAIN_ATTEST_BACKUP_VERIFIED": "true",
        "OPENBRAIN_ATTEST_RESTORE_DRILL": "true",
        "OPENBRAIN_ATTEST_MONITORING": "true",
        "OPENBRAIN_ATTEST_MIGRATIONS_RECORDED": "true",
    }
    values.update(overrides)
    return values


def test_release_readiness_passes_only_with_complete_configuration_and_attestations():
    report = evaluate_release_readiness(production_env())

    assert report.ready is True
    assert all(check.passed for check in report.checks)


def test_release_readiness_rejects_wildcard_cors_and_weak_key():
    report = evaluate_release_readiness(
        production_env(OPENBRAIN_API_KEY="secret", OPENBRAIN_CORS_ORIGINS="*")
    )

    failures = {check.name for check in report.checks if not check.passed}
    assert report.ready is False
    assert failures == {"strong_api_key", "explicit_cors"}


def test_release_readiness_never_infers_operator_controls():
    values = production_env()
    values.pop("OPENBRAIN_ATTEST_BACKUP_VERIFIED")
    values.pop("OPENBRAIN_ATTEST_RESTORE_DRILL")

    report = evaluate_release_readiness(values)

    failures = {check.name for check in report.checks if not check.passed}
    assert report.ready is False
    assert failures == {"backups_verified", "restore_drill_completed"}
    assert all(
        check.category == "attestation"
        for check in report.checks
        if check.name in failures
    )
