"""Durable, provenance-preserving memory compaction."""

from .engine import CompactionCandidate, build_summary, source_fingerprint

__all__ = ["CompactionCandidate", "build_summary", "source_fingerprint"]
