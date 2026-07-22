"""Database retry and transient-failure classification helpers."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from psycopg2 import errors

T = TypeVar("T")

_RETRYABLE_SQLSTATES = {
    "40001",  # serialization_failure
    "40P01",  # deadlock_detected
    "55P03",  # lock_not_available
}


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff policy for whole transactions."""

    attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0
    jitter_seconds: float = 0.025

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1")
        if min(self.base_delay_seconds, self.max_delay_seconds, self.jitter_seconds) < 0:
            raise ValueError("retry delays cannot be negative")


def is_retryable_database_error(exc: BaseException) -> bool:
    """Return whether PostgreSQL reports a safe whole-transaction retry case."""
    sqlstate = getattr(exc, "pgcode", None) or getattr(exc, "sqlstate", None)
    return sqlstate in _RETRYABLE_SQLSTATES or isinstance(
        exc,
        (errors.SerializationFailure, errors.DeadlockDetected, errors.LockNotAvailable),
    )


def run_transaction_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_uniform: Callable[[float, float], float] = random.uniform,
) -> T:
    """Run an idempotent transaction callback with bounded transient retries.

    The callback must open and finish a complete transaction on every invocation.
    Callers must not use this helper around non-idempotent external side effects.
    """
    selected = policy or RetryPolicy()
    for attempt in range(1, selected.attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= selected.attempts or not is_retryable_database_error(exc):
                raise
            exponential = min(
                selected.max_delay_seconds,
                selected.base_delay_seconds * (2 ** (attempt - 1)),
            )
            sleep(exponential + random_uniform(0, selected.jitter_seconds))
    raise RuntimeError("unreachable retry state")
