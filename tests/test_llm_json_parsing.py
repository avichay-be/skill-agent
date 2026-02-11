"""Tests for LLM client JSON parsing robustness."""

import pytest

from app.services.llm_client import BaseLLMClient, LLMClientError


class _DummyClient(BaseLLMClient):
    """Minimal concrete client for testing _extract_json_from_text."""

    async def generate(self, prompt, document, temperature=0.0, max_tokens=4096):  # type: ignore[override]
        return "", None  # type: ignore[return-value]

    async def extract_json(self, prompt, document, temperature=0.0, max_tokens=4096):  # type: ignore[override]
        return {}, None  # type: ignore[return-value]


@pytest.fixture
def client() -> _DummyClient:
    return _DummyClient()


class TestExtractJsonFromText:
    """Tests for _extract_json_from_text robustness."""

    def test_clean_json(self, client: _DummyClient) -> None:
        assert client._extract_json_from_text('{"key": "value"}') == {"key": "value"}

    def test_json_in_code_block(self, client: _DummyClient) -> None:
        text = '```json\n{"key": "value"}\n```'
        assert client._extract_json_from_text(text) == {"key": "value"}

    def test_json_in_code_block_no_lang(self, client: _DummyClient) -> None:
        text = '```\n{"key": "value"}\n```'
        assert client._extract_json_from_text(text) == {"key": "value"}

    def test_extra_data_after_empty_object(self, client: _DummyClient) -> None:
        """Gemini sometimes returns {}{...actual data...}."""
        text = '{}\n{"projectInfo": {"name": "test"}, "total": 100}'
        result = client._extract_json_from_text(text)
        assert result["projectInfo"]["name"] == "test"
        assert result["total"] == 100

    def test_extra_data_two_objects(self, client: _DummyClient) -> None:
        """Picks the largest JSON object when multiple are present."""
        text = '{"a": 1}\n{"a": 1, "b": 2, "c": 3}'
        result = client._extract_json_from_text(text)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_json_with_trailing_text(self, client: _DummyClient) -> None:
        text = '{"key": "value"}\n\nHere is the explanation...'
        assert client._extract_json_from_text(text) == {"key": "value"}

    def test_json_with_leading_text(self, client: _DummyClient) -> None:
        text = 'Here is the result:\n{"key": "value"}'
        assert client._extract_json_from_text(text) == {"key": "value"}

    def test_nested_json(self, client: _DummyClient) -> None:
        text = '{"outer": {"inner": [1, 2, 3]}}'
        assert client._extract_json_from_text(text) == {"outer": {"inner": [1, 2, 3]}}

    def test_whitespace_padded(self, client: _DummyClient) -> None:
        text = '  \n  {"key": "value"}  \n  '
        assert client._extract_json_from_text(text) == {"key": "value"}

    def test_no_json_raises(self, client: _DummyClient) -> None:
        with pytest.raises(LLMClientError, match="no valid JSON found"):
            client._extract_json_from_text("This is just plain text with no JSON")

    def test_empty_string_raises(self, client: _DummyClient) -> None:
        with pytest.raises(LLMClientError, match="no valid JSON found"):
            client._extract_json_from_text("")

    def test_large_object_preferred_over_small(self, client: _DummyClient) -> None:
        """When empty {} precedes the real object, the real one is returned."""
        text = '{}\n\n{"projectInfo": {"identification": {"projectName": "test"}}, "financialSummary": {"revenue": {"total": 1000}}}'
        result = client._extract_json_from_text(text)
        assert "projectInfo" in result
        assert "financialSummary" in result
