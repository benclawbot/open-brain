"""Knowledge consolidation policies."""

from .assertions import (
    AssertionCandidate,
    ConsolidationAction,
    ConsolidationProposal,
    canonical_value,
    propose_consolidation,
    same_assertion_key,
    survivor_rank,
)

__all__ = [
    "AssertionCandidate",
    "ConsolidationAction",
    "ConsolidationProposal",
    "canonical_value",
    "propose_consolidation",
    "same_assertion_key",
    "survivor_rank",
]
