"""Tests for Skill Executor."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.execution import ExecutionRequest, ExecutionStatus, TokenUsage
from app.models.schema import MergeStrategy
from app.services.executor import SkillExecutor


class TestSkillExecutor:
    """Tests for SkillExecutor class."""

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

        with patch("app.services.executor.LLMClientFactory") as factory:
            factory.get_client.return_value = mock_client
            yield factory

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_registry, mock_llm_factory):
        """Test successful execution."""
        settings = MagicMock()
        settings.default_vendor = "anthropic"
        settings.default_model = None

        executor = SkillExecutor(registry=mock_registry, settings=settings)

        request = ExecutionRequest(
            document="Test document content",
            schema_id="test_schema",
        )

        response = await executor.execute(request)

        assert response.status in [ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL]
        assert response.schema_id == "test_schema"
        assert response.metadata.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_specific_skills(self, mock_registry, mock_llm_factory):
        """Test executing specific skills only."""
        settings = MagicMock()
        settings.default_vendor = "anthropic"
        settings.default_model = None

        executor = SkillExecutor(registry=mock_registry, settings=settings)

        request = ExecutionRequest(
            document="Test document",
            schema_id="test_schema",
            skill_ids=["skill_1"],
        )

        response = await executor.execute(request)

        # Should only execute skill_1
        assert len(response.skill_results) == 1
        assert response.skill_results[0].skill_id == "skill_1"

    @pytest.mark.asyncio
    async def test_execute_schema_not_found(self, mock_registry):
        """Test execution with non-existent schema."""
        settings = MagicMock()
        executor = SkillExecutor(registry=mock_registry, settings=settings)

        request = ExecutionRequest(
            document="Test",
            schema_id="nonexistent",
        )

        response = await executor.execute(request)

        assert response.status == ExecutionStatus.FAILED
        assert "not found" in response.error.lower()

    def test_merge_results_first_wins(self):
        """Test merge strategy: first wins."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        executor = SkillExecutor()

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

        merged = executor._merge_results(results, schema)

        assert merged["key"] == "first"  # First wins
        assert merged["unique1"] == "a"
        assert merged["unique2"] == "b"

    def test_merge_results_last_wins(self):
        """Test merge strategy: last wins."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        executor = SkillExecutor()

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

        merged = executor._merge_results(results, schema)

        assert merged["key"] == "second"  # Last wins

    def test_merge_results_deep_merge(self):
        """Test merge strategy: deep merge."""
        from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
        from app.models.skill import SkillExecutionResult

        executor = SkillExecutor()

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

        merged = executor._merge_results(results, schema)

        assert merged["nested"]["a"] == 1
        assert merged["nested"]["b"] == 2
        assert merged["nested"]["c"] == 3

    def test_get_nested_value(self):
        """Test getting nested values from dict."""
        executor = SkillExecutor()

        data = {"level1": {"level2": {"value": 42}}, "simple": "test"}

        assert executor._get_nested_value(data, "simple") == "test"
        assert executor._get_nested_value(data, "level1.level2.value") == 42
        assert executor._get_nested_value(data, "nonexistent") is None
        assert executor._get_nested_value(data, "level1.nonexistent") is None
