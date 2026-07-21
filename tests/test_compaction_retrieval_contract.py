from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "src" / "context" / "builder.py").read_text()
QUERIES = (ROOT / "src" / "db" / "compaction_queries.py").read_text()


def test_retrieval_reads_only_active_rollups():
    assert "WHERE status='active'" in QUERIES
    assert "fetch_active_compactions" in BUILDER


def test_rollup_metadata_exposes_provenance_without_raw_event_duplication():
    assert '"derived": True' in BUILDER
    assert '"source_event_count"' in BUILDER
    assert '"source_fingerprint"' in BUILDER
    assert "raw source events" in BUILDER


def test_regeneration_supersedes_prior_active_rollups():
    assert "SET status='superseded', superseded_by=%s" in QUERIES
    assert "source_fingerprint(candidates)" in QUERIES
