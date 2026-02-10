"""Tests for LLMClientFactory cache eviction."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_client import LLMClientFactory


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    """Reset the factory cache before and after each test."""
    LLMClientFactory.clear_cache()
    yield
    LLMClientFactory.clear_cache()


def _make_settings(**overrides: object) -> MagicMock:
    settings = MagicMock()
    settings.anthropic_api_key = overrides.get("anthropic_api_key", "key")
    settings.anthropic_model = "claude-sonnet-4-20250514"
    settings.openai_api_key = overrides.get("openai_api_key", "key")
    settings.openai_model = "gpt-4o"
    settings.google_api_key = overrides.get("google_api_key", "key")
    settings.gemini_model = "gemini-2.0-flash"
    return settings


class TestLLMClientFactoryCache:
    """Tests for LRU cache eviction in LLMClientFactory."""

    @patch("app.services.llm_client.AnthropicClient")
    def test_cache_returns_same_client(self, mock_cls: MagicMock) -> None:
        """Repeated calls with same vendor+model return the cached instance."""
        settings = _make_settings()
        c1 = LLMClientFactory.get_client("anthropic", settings=settings)
        c2 = LLMClientFactory.get_client("anthropic", settings=settings)
        assert c1 is c2
        assert mock_cls.call_count == 1

    @patch("app.services.llm_client.AnthropicClient")
    def test_cache_hit_refreshes_lru_order(self, mock_cls: MagicMock) -> None:
        """Accessing an existing entry moves it to the end (most-recently-used)."""
        settings = _make_settings()
        LLMClientFactory.get_client("anthropic", model="m1", settings=settings)
        LLMClientFactory.get_client("anthropic", model="m2", settings=settings)

        # Access m1 again — it should move to end
        LLMClientFactory.get_client("anthropic", model="m1", settings=settings)

        keys = list(LLMClientFactory._clients.keys())
        assert keys == ["anthropic:m2", "anthropic:m1"]

    @patch("app.services.llm_client.AnthropicClient")
    def test_evicts_lru_when_over_capacity(self, mock_cls: MagicMock) -> None:
        """Oldest entry is evicted when cache exceeds max size."""
        settings = _make_settings()
        original_max = LLMClientFactory._max_cache_size
        LLMClientFactory._max_cache_size = 3
        try:
            LLMClientFactory.get_client("anthropic", model="m1", settings=settings)
            LLMClientFactory.get_client("anthropic", model="m2", settings=settings)
            LLMClientFactory.get_client("anthropic", model="m3", settings=settings)

            # This should evict m1
            LLMClientFactory.get_client("anthropic", model="m4", settings=settings)

            assert "anthropic:m1" not in LLMClientFactory._clients
            assert len(LLMClientFactory._clients) == 3
            assert list(LLMClientFactory._clients.keys()) == [
                "anthropic:m2",
                "anthropic:m3",
                "anthropic:m4",
            ]
        finally:
            LLMClientFactory._max_cache_size = original_max

    @patch("app.services.llm_client.AnthropicClient")
    def test_recently_used_not_evicted(self, mock_cls: MagicMock) -> None:
        """A recently accessed entry survives eviction."""
        settings = _make_settings()
        original_max = LLMClientFactory._max_cache_size
        LLMClientFactory._max_cache_size = 3
        try:
            LLMClientFactory.get_client("anthropic", model="m1", settings=settings)
            LLMClientFactory.get_client("anthropic", model="m2", settings=settings)
            LLMClientFactory.get_client("anthropic", model="m3", settings=settings)

            # Touch m1 so it becomes most-recently-used
            LLMClientFactory.get_client("anthropic", model="m1", settings=settings)

            # Adding m4 should evict m2 (the true LRU), not m1
            LLMClientFactory.get_client("anthropic", model="m4", settings=settings)

            assert "anthropic:m1" in LLMClientFactory._clients
            assert "anthropic:m2" not in LLMClientFactory._clients
        finally:
            LLMClientFactory._max_cache_size = original_max

    def test_clear_cache_empties_dict(self) -> None:
        """clear_cache removes all entries."""
        LLMClientFactory._clients["test:key"] = MagicMock()  # type: ignore[assignment]
        LLMClientFactory.clear_cache()
        assert len(LLMClientFactory._clients) == 0
