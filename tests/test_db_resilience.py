from types import SimpleNamespace

import pytest

from src.db.connection import DatabaseConfig, _positive_int_env
from src.db.resilience import RetryPolicy, is_retryable_database_error, run_transaction_with_retry


def test_retry_policy_retries_transient_sqlstate_without_real_sleep():
    attempts = []
    sleeps = []

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            error = RuntimeError("serialization conflict")
            error.pgcode = "40001"
            raise error
        return "ok"

    result = run_transaction_with_retry(
        operation,
        policy=RetryPolicy(attempts=3, base_delay_seconds=0.1, jitter_seconds=0),
        sleep=sleeps.append,
        random_uniform=lambda _low, _high: 0,
    )

    assert result == "ok"
    assert len(attempts) == 3
    assert sleeps == [0.1, 0.2]


def test_retry_policy_does_not_retry_non_transient_failures():
    attempts = []

    def operation():
        attempts.append(1)
        raise ValueError("invalid data")

    with pytest.raises(ValueError):
        run_transaction_with_retry(operation, sleep=lambda _seconds: None)

    assert len(attempts) == 1


def test_retryability_recognizes_supported_sqlstates():
    for sqlstate in ("40001", "40P01", "55P03"):
        assert is_retryable_database_error(SimpleNamespace(pgcode=sqlstate))
    assert not is_retryable_database_error(SimpleNamespace(pgcode="23505"))


def test_positive_integer_environment_validation(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_TEST_INT", "4")
    assert _positive_int_env("OPENBRAIN_TEST_INT", 1) == 4

    monkeypatch.setenv("OPENBRAIN_TEST_INT", "0")
    with pytest.raises(ValueError):
        _positive_int_env("OPENBRAIN_TEST_INT", 1)


def test_database_config_rejects_inverted_pool_bounds(monkeypatch):
    DatabaseConfig._instance = None
    monkeypatch.setenv("DB_POOL_MIN", "5")
    monkeypatch.setenv("DB_POOL_MAX", "2")
    with pytest.raises(ValueError, match="DB_POOL_MIN"):
        DatabaseConfig()
    DatabaseConfig._instance = None
