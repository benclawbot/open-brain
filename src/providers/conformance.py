"""Reusable conformance checks for Open Brain provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import ValidationError

from .contracts import MemoryProvider, ProviderCapability, RecallRequest, RememberRequest


@dataclass(frozen=True)
class ConformanceFailure:
    check: str
    detail: str


@dataclass(frozen=True)
class ConformanceReport:
    provider_id: str
    passed: tuple[str, ...] = field(default_factory=tuple)
    failures: tuple[ConformanceFailure, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.failures

    def require_success(self) -> None:
        if self.failures:
            details = "; ".join(f"{item.check}: {item.detail}" for item in self.failures)
            raise AssertionError(f"provider conformance failed: {details}")


def run_provider_conformance(
    provider: MemoryProvider,
    *,
    recall_request: RecallRequest | None = None,
    remember_request: RememberRequest | None = None,
) -> ConformanceReport:
    """Exercise the mandatory provider contract without assuming a host agent.

    Network-backed adapters should inject a mock transport or test server. The runner
    validates descriptor consistency, declared capabilities, response shapes, and
    deterministic duplicate-safe remember behavior.
    """

    passed: list[str] = []
    failures: list[ConformanceFailure] = []
    descriptor = provider.descriptor

    def check(name: str, operation: Callable[[], None]) -> None:
        try:
            operation()
        except Exception as exc:  # noqa: BLE001 - report all adapter contract failures
            failures.append(ConformanceFailure(name, f"{type(exc).__name__}: {exc}"))
        else:
            passed.append(name)

    check("protocol", lambda: _require(isinstance(provider, MemoryProvider), "not a MemoryProvider"))
    check("descriptor", lambda: _validate_descriptor(descriptor))
    check("health", lambda: _validate_mapping(provider.health(), "health"))

    if ProviderCapability.RECALL in descriptor.capabilities:
        request = recall_request or RecallRequest()
        check("recall", lambda: _validate_mapping(provider.recall(request), "recall"))

    if ProviderCapability.REMEMBER in descriptor.capabilities:
        request = remember_request or RememberRequest(
            event_type="conformance.probe",
            idempotency_key=f"conformance:{descriptor.provider_id}:probe",
            payload={"probe": True},
        )
        check("remember", lambda: _validate_mapping(provider.remember(request), "remember"))
        check("remember_duplicate", lambda: _validate_mapping(provider.remember(request), "remember_duplicate"))

    return ConformanceReport(
        provider_id=descriptor.provider_id,
        passed=tuple(passed),
        failures=tuple(failures),
    )


def _validate_descriptor(descriptor: Any) -> None:
    try:
        validated = descriptor.__class__.model_validate(descriptor.model_dump())
    except (AttributeError, ValidationError) as exc:
        raise AssertionError("descriptor is not a valid ProviderDescriptor") from exc
    _require(bool(validated.provider_id), "provider_id is empty")
    _require(bool(validated.version), "version is empty")


def _validate_mapping(value: Any, name: str) -> None:
    _require(isinstance(value, dict), f"{name} must return a dict")


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)
