"""Regression tests for API search distance and embedder environment settings."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.embedder import EmbedderConfig


def _memory():
    return {
        "id": str(uuid4()),
        "source": "api",
        "captured_by": None,
        "content": "the roadmap",
        "tags": [],
        "entities": {},
        "importance": 0.5,
        "created_at": datetime.now(timezone.utc),
    }


def test_search_exposes_cosine_distance_and_get_does_not_change_shape():
    memory = _memory()
    # The shared API app can require an API key in CI; exercise the actual
    # routes with the app's configured test credential, when present.
    configured_key = app.state.operational_settings.api_key
    headers = {"X-API-Key": configured_key} if configured_key else {}
    with (
        patch("src.api.main.search_memories", return_value=[{**memory, "score": 0.26}]),
        patch("src.api.main.create_embedding", return_value=[0.2, 0.3]),
    ):
        result = TestClient(app).post("/memories/search", json={"query": "roadmap"}, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()[0]["score"] == pytest.approx(0.26)

    with patch("src.api.main.get_recent_memories", return_value=[memory]):
        result = TestClient(app).get("/memories", headers=headers)
    assert result.status_code == 200, result.text
    assert "score" not in result.json()[0]


def test_embedder_respects_environment_precedence_and_blank_values(monkeypatch, tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text(
        "embedder:\n  provider: ollama\n  model: local-model\n  dimensions: 768\n",
        encoding="utf-8",
    )
    for name in ("EMBEDDER_PROVIDER", "EMBEDDER_MODEL", "EMBEDDER_DIMENSIONS"):
        monkeypatch.delenv(name, raising=False)

    configured = EmbedderConfig(str(path))
    assert (configured.provider, configured.model, configured.dimensions) == (
        "ollama", "local-model", 768
    )

    monkeypatch.setenv("EMBEDDER_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDER_MODEL", "new-model")
    monkeypatch.setenv("EMBEDDER_DIMENSIONS", "1024")
    configured = EmbedderConfig(str(path))
    assert (configured.provider, configured.model, configured.dimensions) == (
        "openai", "new-model", 1024
    )

    monkeypatch.setenv("EMBEDDER_PROVIDER", "  ")
    monkeypatch.setenv("EMBEDDER_MODEL", "")
    monkeypatch.setenv("EMBEDDER_DIMENSIONS", "")
    configured = EmbedderConfig(str(path))
    assert (configured.provider, configured.model, configured.dimensions) == (
        "ollama", "local-model", 768
    )


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_embedder_rejects_invalid_dimensions(monkeypatch, tmp_path, value):
    path = tmp_path / "settings.yaml"
    path.write_text("embedder: {provider: ollama, model: test, dimensions: 768}\n")
    monkeypatch.setenv("EMBEDDER_DIMENSIONS", value)
    with pytest.raises(ValueError):
        EmbedderConfig(str(path))
