"""Machine-readable production release readiness validation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Mapping


_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    category: str
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    checks: tuple[ReadinessCheck, ...]

    def as_dict(self) -> dict:
        return {"ready": self.ready, "checks": [asdict(check) for check in self.checks]}


def _enabled(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in _TRUE


def evaluate_release_readiness(env: Mapping[str, str] | None = None) -> ReadinessReport:
    """Evaluate production configuration and explicit operator attestations.

    The command deliberately does not infer that backups, restore drills, TLS, or
    monitoring exist. Those controls must be attested explicitly by the operator
    that performed or verified them.
    """
    values = os.environ if env is None else env
    environment = values.get("OPENBRAIN_ENV", "").strip().lower()
    api_key = values.get("OPENBRAIN_API_KEY", "")
    cors = [item.strip() for item in values.get("OPENBRAIN_CORS_ORIGINS", "").split(",") if item.strip()]

    checks = (
        ReadinessCheck(
            "production_environment",
            environment in {"production", "prod"},
            "automatic",
            "OPENBRAIN_ENV must be production or prod",
        ),
        ReadinessCheck(
            "authentication_required",
            _enabled(values, "OPENBRAIN_AUTH_REQUIRED"),
            "automatic",
            "OPENBRAIN_AUTH_REQUIRED must be enabled",
        ),
        ReadinessCheck(
            "strong_api_key",
            len(api_key) >= 32 and api_key.lower() not in {"changeme", "secret", "test"},
            "automatic",
            "OPENBRAIN_API_KEY must contain at least 32 non-placeholder characters",
        ),
        ReadinessCheck(
            "explicit_cors",
            bool(cors) and "*" not in cors,
            "automatic",
            "OPENBRAIN_CORS_ORIGINS must be an explicit non-wildcard allow-list",
        ),
        ReadinessCheck(
            "tls_terminated",
            _enabled(values, "OPENBRAIN_ATTEST_TLS"),
            "attestation",
            "Operator must attest that maintained TLS termination is configured",
        ),
        ReadinessCheck(
            "backups_verified",
            _enabled(values, "OPENBRAIN_ATTEST_BACKUP_VERIFIED"),
            "attestation",
            "Operator must attest that a current encrypted backup is readable",
        ),
        ReadinessCheck(
            "restore_drill_completed",
            _enabled(values, "OPENBRAIN_ATTEST_RESTORE_DRILL"),
            "attestation",
            "Operator must attest that the documented restore drill completed",
        ),
        ReadinessCheck(
            "monitoring_configured",
            _enabled(values, "OPENBRAIN_ATTEST_MONITORING"),
            "attestation",
            "Operator must attest that readiness, latency, and error alerts are active",
        ),
        ReadinessCheck(
            "migration_state_recorded",
            _enabled(values, "OPENBRAIN_ATTEST_MIGRATIONS_RECORDED"),
            "attestation",
            "Operator must attest that release and migration checksum state were recorded",
        ),
    )
    return ReadinessReport(ready=all(check.passed for check in checks), checks=checks)


def main() -> int:
    report = evaluate_release_readiness()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
