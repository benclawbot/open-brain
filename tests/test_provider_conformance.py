from __future__ import annotations

from typing import Any

from src.providers import (
    MemoryProvider,
    ProviderCapability,
    ProviderDescriptor,
    RecallRequest,
    RememberRequest,
    run_provider_conformance,
)


class FakeProvider:
    descriptor = ProviderDescriptor(
        provider_id="fake-agent",
        display_name="Fake Agent",
        version="1.0.0",
        capabilities={ProviderCapability.RECALL, ProviderCapability.REMEMBER},
    )

    def __init__(self) -> None:
        self.remembered: list[str] = []

    def health(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def recall(self, request: RecallRequest) -> dict[str, Any]:
        return {"items": [], "token_budget": request.token_budget}

    def remember(self, request: RememberRequest) -> dict[str, Any]:
        duplicate = request.idempotency_key in self.remembered
        self.remembered.append(request.idempotency_key)
        return {"status": "stored", "duplicate": duplicate}

    def close(self) -> None:
        return None


class BrokenProvider(FakeProvider):
    def health(self) -> list[str]:  # type: ignore[override]
        return ["not", "a", "mapping"]


def test_conformance_runner_accepts_valid_provider() -> None:
    provider = FakeProvider()

    assert isinstance(provider, MemoryProvider)
    report = run_provider_conformance(provider)

    assert report.ok
    assert report.provider_id == "fake-agent"
    assert report.failures == ()
    assert "remember_duplicate" in report.passed


def test_conformance_runner_reports_failures_without_hiding_other_checks() -> None:
    report = run_provider_conformance(BrokenProvider())

    assert not report.ok
    assert any(item.check == "health" for item in report.failures)
    assert "recall" in report.passed
    assert "remember" in report.passed


def test_conformance_report_can_fail_a_ci_gate() -> None:
    report = run_provider_conformance(BrokenProvider())

    try:
        report.require_success()
    except AssertionError as exc:
        assert "health" in str(exc)
    else:
        raise AssertionError("require_success should fail for a broken provider")
