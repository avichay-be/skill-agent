"""Tests for shared execution utilities."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.execution import TokenUsage
from app.models.schema import MergeStrategy
from app.services.execution_utils import (
    execute_single_skill,
    get_default_model_for_vendor,
    get_nested_value,
    merge_results,
)


class TestExecutionUtils:
    """Tests for shared execution helpers."""

    @pytest.fixture
    def mock_registry(self, temp_skills_dir: Path):
        """Create a mock registry with test schema."""
        from unittest.mock import patch

        from app.services.skill_registry import SkillRegistry

        SkillRegistry.reset()

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""
        settings.default_vendor = "anthropic"
        settings.default_model = None
        settings.default_timeout_seconds = 60
        settings.default_retry_count = 2
        settings.anthropic_model = "claude-sonnet-4-20250514"
        settings.openai_model = "gpt-4o"
        settings.gemini_model = "gemini-2.0-flash"

        with patch("app.services.skill_registry.get_settings", return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()
            yield registry

        SkillRegistry.reset()

    @pytest.fixture
    def mock_llm_factory(self):
        """Mock LLM client factory."""
        mock_client = AsyncMock()
        mock_client.extract_json = AsyncMock(
            return_value=(
                {"field1": "extracted_value"},
                TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            )
        )

        with patch("app.services.execution_utils.LLMClientFactory") as factory:
            factory.get_client.return_value = mock_client
            yield factory

    @pytest.mark.asyncio
    async def test_execute_single_skill_success(self, mock_registry, mock_llm_factory):
        """Test successful single-skill execution."""
        skill = mock_registry.get_schema_or_raise("test_schema").get_active_skills()[0]
        settings = MagicMock()
        settings.default_vendor = "anthropic"
        settings.default_model = None
        settings.anthropic_model = "claude-sonnet-4-20250514"
        settings.openai_model = "gpt-4o"
        settings.gemini_model = "gemini-2.0-flash"

        result = await execute_single_skill(
            skill=skill,
            document="Test document content",
            default_vendor="anthropic",
            default_model=None,
            settings=settings,
        )

        assert result.success is True
        assert result.skill_id == skill.id
        assert result.execution_time_ms >= 0

    def test_merge_results_first_wins(self):
        """Test merge strategy: first wins."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        config = SchemaConfig(
            schema_id="test",
            version="1.0",
            name="Test",
            post_processing=PostProcessing(merge_strategy=MergeStrategy.FIRST_WINS),
        )

        schema = LoadedSchema(
            config=config,
            skills={},
            git_commit="abc",
            source_path="/test",
        )

        results = [
            SkillExecutionResult(
                skill_id="s1",
                success=True,
                data={"key": "first", "unique1": "a"},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
            SkillExecutionResult(
                skill_id="s2",
                success=True,
                data={"key": "second", "unique2": "b"},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
        ]

        merged = merge_results(results, schema.config.post_processing.merge_strategy)

        assert merged["key"] == "first"  # First wins
        assert merged["unique1"] == "a"
        assert merged["unique2"] == "b"

    def test_merge_results_last_wins(self):
        """Test merge strategy: last wins."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        config = SchemaConfig(
            schema_id="test",
            version="1.0",
            name="Test",
            post_processing=PostProcessing(merge_strategy=MergeStrategy.LAST_WINS),
        )

        schema = LoadedSchema(
            config=config,
            skills={},
            git_commit="abc",
            source_path="/test",
        )

        results = [
            SkillExecutionResult(
                skill_id="s1",
                success=True,
                data={"key": "first"},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
            SkillExecutionResult(
                skill_id="s2",
                success=True,
                data={"key": "second"},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
        ]

        merged = merge_results(results, schema.config.post_processing.merge_strategy)

        assert merged["key"] == "second"  # Last wins

    def test_merge_results_deep_merge(self):
        """Test merge strategy: deep merge."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        config = SchemaConfig(
            schema_id="test",
            version="1.0",
            name="Test",
            post_processing=PostProcessing(merge_strategy=MergeStrategy.MERGE_DEEP),
        )

        schema = LoadedSchema(
            config=config,
            skills={},
            git_commit="abc",
            source_path="/test",
        )

        results = [
            SkillExecutionResult(
                skill_id="s1",
                success=True,
                data={"nested": {"a": 1, "b": 2}},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
            SkillExecutionResult(
                skill_id="s2",
                success=True,
                data={"nested": {"c": 3}},
                execution_time_ms=100,
                model_used="test",
                vendor_used="test",
            ),
        ]

        merged = merge_results(results, schema.config.post_processing.merge_strategy)

        assert merged["nested"]["a"] == 1
        assert merged["nested"]["b"] == 2
        assert merged["nested"]["c"] == 3

    def test_get_nested_value(self):
        """Test getting nested values from dict."""
        data = {"level1": {"level2": {"value": 42}}, "simple": "test"}

        assert get_nested_value(data, "simple") == "test"
        assert get_nested_value(data, "level1.level2.value") == 42
        assert get_nested_value(data, "nonexistent") is None
        assert get_nested_value(data, "level1.nonexistent") is None

    def test_get_default_model_for_vendor(self):
        """Test vendor-to-model resolution."""
        settings = MagicMock(
            anthropic_model="claude-sonnet-4-20250514",
            openai_model="gpt-4o",
            gemini_model="gemini-2.0-flash",
        )

        assert get_default_model_for_vendor("anthropic", settings) == "claude-sonnet-4-20250514"
        assert get_default_model_for_vendor("openai", settings) == "gpt-4o"
        assert get_default_model_for_vendor("gemini", settings) == "gemini-2.0-flash"
