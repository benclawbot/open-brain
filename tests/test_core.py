"""
Core tests for Open Brain.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

class TestConfig:
    """Test configuration loading."""

    def test_load_settings(self):
        """Test that settings.yaml loads correctly."""
        import yaml

        config_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'config', 'settings.yaml'
        )

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'database' in config
        assert 'embedder' in config
        assert 'mcp' in config
        assert 'tags' in config


class TestEntityExtractor:
    """Test entity extraction."""

    def test_email_extraction(self):
        from src.extractors.entities import extract_entities

        entities = extract_entities("Contact me at test@example.com")
        assert 'test@example.com' in entities['emails']

    def test_url_extraction(self):
        from src.extractors.entities import extract_entities

        entities = extract_entities("Check out https://github.com/test/repo")
        assert any('github.com' in url for url in entities['urls'])

    def test_hashtag_extraction(self):
        from src.extractors.entities import extract_entities

        entities = extract_entities("Great #python #ai project")
        assert '#python' in entities['hashtags']
        assert '#ai' in entities['hashtags']

    def test_technology_extraction(self):
        from src.extractors.entities import extract_entities

        entities = extract_entities("Built with Python and React")
        assert 'python' in entities['technologies']
        assert 'react' in entities['technologies']


class TestTagger:
    """Test auto-tagging."""

    def test_keyword_tagging(self):
        from src.extractors.tagger import auto_tag

        tags = auto_tag("Working on a Python bug fix")
        assert 'python' in tags
        assert 'bug' in tags

    def test_pattern_tagging(self):
        from src.extractors.tagger import auto_tag

        tags = auto_tag("How to fix this error?")
        assert 'error' in tags
        assert 'question' in tags

    def test_user_tags(self):
        from src.extractors.tagger import auto_tag

        tags = auto_tag("Some note", user_tags=['important', 'review'])
        assert 'important' in tags
        assert 'review' in tags

    def test_deny_list(self):
        from src.extractors.tagger import Tagger

        tagger = Tagger()
        tags = tagger.tag("test", user_tags=['password', 'valid_tag'])
        assert 'password' not in tags
        assert 'valid_tag' in tags


class TestEmbedder:
    """Test embedder functionality."""

    @staticmethod
    def _ollama_config():
        return Mock(
            model='nomic-embed-text',
            ollama_base_url='http://localhost:11434',
            dimensions=768,
        )

    @patch('requests.post')
    def test_embed_creation(self, mock_post):
        from src.embedder import OllamaEmbedder

        mock_response = Mock()
        mock_response.json.return_value = {'embedding': [0.1] * 768}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        embedder = OllamaEmbedder(self._ollama_config())
        embedding = embedder.embed("test text")

        assert len(embedding) == 768
        assert mock_post.called

    @patch('requests.post')
    def test_batch_embedding(self, mock_post):
        from src.embedder import OllamaEmbedder

        mock_response = Mock()
        mock_response.json.return_value = {'embedding': [0.1] * 768}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        embedder = OllamaEmbedder(self._ollama_config())
        embeddings = embedder.embed_batch(["text1", "text2"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 768


class TestAnalytics:
    """Test analytics functions."""

    def test_trend_analyzer_init(self):
        from src.analytics.trends import TrendAnalyzer

        analyzer = TrendAnalyzer(weeks=4)
        assert analyzer.weeks == 4


class TestMemoryFormatting:
    """Test memory formatting functions."""

    def test_format_empty_list(self):
        from src.main import format_memory_list

        result = format_memory_list([])
        assert "No memories found" in result

    def test_format_memory_list(self):
        from src.main import format_memory_list

        memories = [
            {
                'id': str(uuid.uuid4()),
                'source': 'test',
                'content': 'Test content',
                'tags': ['test'],
                'created_at': datetime.now(timezone.utc)
            }
        ]

        result = format_memory_list(memories)
        assert 'ID:' in result
        assert 'Source: test' in result
        assert 'Test content' in result


class TestDatabaseQueries:
    """Test database query functions with realistic cursor mocks."""

    @patch('src.db.queries.get_db_cursor')
    def test_search_memories(self, mock_cursor):
        from src.db import queries

        mock_ctx = Mock()
        mock_ctx.__enter__ = Mock(return_value=mock_ctx)
        mock_ctx.__exit__ = Mock(return_value=False)
        mock_cursor.return_value = mock_ctx
        mock_ctx.fetchall.return_value = []

        results = queries.search_memories("test", limit=5)
        assert isinstance(results, list)

    @patch('src.db.queries.get_db_cursor')
    def test_get_memory_stats(self, mock_cursor):
        from src.db import queries

        mock_ctx = Mock()
        mock_ctx.__enter__ = Mock(return_value=mock_ctx)
        mock_ctx.__exit__ = Mock(return_value=False)
        mock_cursor.return_value = mock_ctx
        mock_ctx.fetchone.side_effect = [
            {'total': 100},
            {'count': 25},
            {'count': 30},
        ]
        mock_ctx.fetchall.side_effect = [
            [{'source': 'test', 'count': 50}],
            [{'tag': 'python', 'count': 10}],
        ]

        stats = queries.get_memory_stats()
        assert stats['total'] == 100
        assert stats['by_source'] == {'test': 50}
        assert stats['top_tags'] == {'python': 10}


def run_tests():
    pytest.main([__file__, '-v'])


if __name__ == "__main__":
    run_tests()
