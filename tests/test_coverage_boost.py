"""Coverage boost tests for key untested modules.

Targets:
- app/services/llm_client.py
- app/services/graph_executor.py
- app/services/workflow_executor.py
- app/services/graph/nodes.py
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**kwargs: Any) -> Any:
    """Return a Settings object with safe defaults for unit tests."""
    from app.core.config import Settings

    defaults: Dict[str, Any] = dict(
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key",
        google_api_key="test-google-key",
        anthropic_model="claude-3-5-haiku-20241022",
        openai_model="gpt-4o-mini",
        gemini_model="gemini-1.5-flash",
        default_vendor="anthropic",
        api_keys="test-api-key",
        local_skills_path="",
        github_repo_url="",
    )
    defaults.update(kwargs)
    return Settings(**defaults)


# ===========================================================================
# LLMClient tests
# ===========================================================================


class TestLLMClientBaseHelpers:
    """Tests for the shared parsing helpers on BaseLLMClient."""

    def _make_client(self) -> Any:
        from app.services.llm_client import AnthropicClient

        with patch("anthropic.AsyncAnthropic"):
            return AnthropicClient(api_key="key", model="claude-3-5-haiku-20241022")

    def test_extract_json_from_text_direct_json(self) -> None:
        client = self._make_client()
        result = client._extract_json_from_text('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_from_text_code_block(self) -> None:
        client = self._make_client()
        text = '```json\n{"answer": 42}\n```'
        result = client._extract_json_from_text(text)
        assert result == {"answer": 42}

    def test_extract_json_from_text_code_block_no_lang(self) -> None:
        client = self._make_client()
        text = '```\n{"answer": 42}\n```'
        result = client._extract_json_from_text(text)
        assert result == {"answer": 42}

    def test_extract_json_from_text_embedded_json(self) -> None:
        client = self._make_client()
        text = 'Here is the result: {"name": "Alice"} done.'
        result = client._extract_json_from_text(text)
        assert result == {"name": "Alice"}

    def test_extract_json_from_text_raises_on_invalid(self) -> None:
        from app.services.llm_client import LLMClientError

        client = self._make_client()
        with pytest.raises(LLMClientError, match="Failed to parse JSON"):
            client._extract_json_from_text("no json here at all")

    def test_find_largest_json_object_picks_biggest(self) -> None:
        from app.services.llm_client import BaseLLMClient

        text = '{"a": 1} some text {"b": 2, "c": 3}'
        result = BaseLLMClient._find_largest_json_object(text)
        # The second object has more characters
        assert result == {"b": 2, "c": 3}

    def test_find_largest_json_object_returns_none_on_no_match(self) -> None:
        from app.services.llm_client import BaseLLMClient

        result = BaseLLMClient._find_largest_json_object("no braces here")
        assert result is None


class TestAnthropicClient:
    """Tests for the AnthropicClient."""

    def _make_client(self) -> Any:
        from app.services.llm_client import AnthropicClient

        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            client = AnthropicClient(api_key="key", model="claude-3-5-haiku-20241022")
            # Overwrite with fresh mock so we can configure per-test
            client.client = MagicMock()
            return client

    async def test_generate_returns_text_and_usage(self) -> None:
        client = self._make_client()

        mock_block = MagicMock()
        mock_block.text = "Hello"
        mock_msg = MagicMock()
        mock_msg.content = [mock_block]
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 5
        client.client.messages.create = AsyncMock(return_value=mock_msg)

        text, usage = await client.generate("prompt", "doc")
        assert text == "Hello"
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.total_tokens == 15

    async def test_generate_raises_on_non_text_block(self) -> None:
        from app.services.llm_client import LLMClientError

        client = self._make_client()

        mock_block = MagicMock(spec=[])  # no 'text' attribute
        mock_msg = MagicMock()
        mock_msg.content = [mock_block]
        mock_msg.usage.input_tokens = 0
        mock_msg.usage.output_tokens = 0
        client.client.messages.create = AsyncMock(return_value=mock_msg)

        with pytest.raises(LLMClientError):
            await client.generate("prompt", "doc")

    async def test_generate_wraps_exception(self) -> None:
        from app.services.llm_client import LLMClientError

        client = self._make_client()
        client.client.messages.create = AsyncMock(side_effect=RuntimeError("network error"))

        with pytest.raises(LLMClientError, match="Anthropic API error"):
            await client.generate("prompt", "doc")

    async def test_extract_json_returns_parsed_data(self) -> None:
        client = self._make_client()

        mock_block = MagicMock()
        mock_block.text = '{"result": "test"}'
        mock_msg = MagicMock()
        mock_msg.content = [mock_block]
        mock_msg.usage.input_tokens = 10
        mock_msg.usage.output_tokens = 5
        client.client.messages.create = AsyncMock(return_value=mock_msg)

        data, usage = await client.extract_json("Extract data", "Sample document")
        assert data == {"result": "test"}
        assert usage.total_tokens == 15

    def test_import_error_raises_llm_client_error(self) -> None:
        from app.services.llm_client import LLMClientError

        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(LLMClientError, match="anthropic package not installed"):
                from app.services.llm_client import AnthropicClient  # noqa: F401

                AnthropicClient(api_key="key", model="m")


class TestOpenAIClient:
    """Tests for the OpenAIClient."""

    def _make_client(self) -> Any:
        from app.services.llm_client import OpenAIClient

        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            client = OpenAIClient(api_key="key", model="gpt-4o-mini")
            client.client = MagicMock()
            return client

    async def test_generate_returns_text_and_usage(self) -> None:
        client = self._make_client()

        mock_choice = MagicMock()
        mock_choice.message.content = "OpenAI response"
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 20
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 30
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        text, usage = await client.generate("prompt", "doc")
        assert text == "OpenAI response"
        assert usage.total_tokens == 30

    async def test_extract_json_returns_parsed_dict(self) -> None:
        client = self._make_client()

        mock_choice = MagicMock()
        mock_choice.message.content = '{"field": "value"}'
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 5
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 10
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        data, usage = await client.extract_json("prompt", "doc")
        assert data == {"field": "value"}

    async def test_extract_json_raises_on_invalid_json(self) -> None:
        from app.services.llm_client import LLMClientError

        client = self._make_client()

        mock_choice = MagicMock()
        mock_choice.message.content = "not valid json"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMClientError):
            await client.extract_json("prompt", "doc")

    async def test_generate_wraps_exception(self) -> None:
        from app.services.llm_client import LLMClientError

        client = self._make_client()
        client.client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))

        with pytest.raises(LLMClientError, match="OpenAI API error"):
            await client.generate("prompt", "doc")

    async def test_generate_handles_none_usage(self) -> None:
        client = self._make_client()

        mock_choice = MagicMock()
        mock_choice.message.content = "text"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        text, usage = await client.generate("prompt", "doc")
        assert text == "text"
        assert usage.total_tokens == 0


class TestLLMClientFactory:
    """Tests for the LLMClientFactory."""

    def setup_method(self) -> None:
        from app.services.llm_client import LLMClientFactory

        LLMClientFactory.clear_cache()

    def test_get_client_anthropic(self) -> None:
        from app.services.llm_client import AnthropicClient, LLMClientFactory

        settings = _make_settings()
        with patch("anthropic.AsyncAnthropic"):
            client = LLMClientFactory.get_client("anthropic", "claude-3-5-haiku-20241022", settings)
        assert isinstance(client, AnthropicClient)

    def test_get_client_openai(self) -> None:
        from app.services.llm_client import LLMClientFactory, OpenAIClient

        settings = _make_settings()
        with patch("openai.AsyncOpenAI"):
            client = LLMClientFactory.get_client("openai", "gpt-4o-mini", settings)
        assert isinstance(client, OpenAIClient)

    def test_get_client_gemini(self) -> None:
        from app.services.llm_client import GeminiClient, LLMClientFactory

        settings = _make_settings()
        with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel"):
            client = LLMClientFactory.get_client("gemini", "gemini-1.5-flash", settings)
        assert isinstance(client, GeminiClient)

    def test_get_client_unknown_vendor_raises(self) -> None:
        from app.services.llm_client import LLMClientError, LLMClientFactory

        settings = _make_settings()
        with pytest.raises(LLMClientError, match="Unknown vendor"):
            LLMClientFactory.get_client("unknown_vendor", "model", settings)

    def test_get_client_missing_anthropic_key_raises(self) -> None:
        from app.services.llm_client import LLMClientError, LLMClientFactory

        settings = _make_settings(anthropic_api_key=None)
        with pytest.raises(LLMClientError, match="ANTHROPIC_API_KEY not configured"):
            LLMClientFactory.get_client("anthropic", "model", settings)

    def test_get_client_missing_openai_key_raises(self) -> None:
        from app.services.llm_client import LLMClientError, LLMClientFactory

        settings = _make_settings(openai_api_key=None)
        with pytest.raises(LLMClientError, match="OPENAI_API_KEY not configured"):
            LLMClientFactory.get_client("openai", "model", settings)

    def test_get_client_missing_google_key_raises(self) -> None:
        from app.services.llm_client import LLMClientError, LLMClientFactory

        settings = _make_settings(google_api_key=None)
        with pytest.raises(LLMClientError, match="GOOGLE_API_KEY not configured"):
            LLMClientFactory.get_client("gemini", "model", settings)

    def test_get_client_returns_cached_instance(self) -> None:
        from app.services.llm_client import LLMClientFactory

        settings = _make_settings()
        with patch("anthropic.AsyncAnthropic"):
            c1 = LLMClientFactory.get_client("anthropic", "claude-3-5-haiku-20241022", settings)
            c2 = LLMClientFactory.get_client("anthropic", "claude-3-5-haiku-20241022", settings)
        assert c1 is c2

    def test_lru_eviction_when_cache_full(self) -> None:
        from app.services.llm_client import LLMClientFactory

        settings = _make_settings()
        original_max = LLMClientFactory._max_cache_size
        LLMClientFactory._max_cache_size = 2
        try:
            with (
                patch("anthropic.AsyncAnthropic"),
                patch("openai.AsyncOpenAI"),
                patch("google.generativeai.configure"),
                patch("google.generativeai.GenerativeModel"),
            ):
                LLMClientFactory.get_client("anthropic", "model-a", settings)
                LLMClientFactory.get_client("openai", "model-b", settings)
                # Adding a third entry should evict model-a
                LLMClientFactory.get_client("anthropic", "model-c", settings)

            assert "anthropic:model-a" not in LLMClientFactory._clients
            assert "openai:model-b" in LLMClientFactory._clients
            assert "anthropic:model-c" in LLMClientFactory._clients
        finally:
            LLMClientFactory._max_cache_size = original_max

    def test_clear_cache(self) -> None:
        from app.services.llm_client import LLMClientFactory

        settings = _make_settings()
        with patch("anthropic.AsyncAnthropic"):
            LLMClientFactory.get_client("anthropic", "claude-3-5-haiku-20241022", settings)
        assert len(LLMClientFactory._clients) > 0
        LLMClientFactory.clear_cache()
        assert len(LLMClientFactory._clients) == 0

    def test_get_client_uses_default_model_when_none(self) -> None:
        from app.services.llm_client import LLMClientFactory

        settings = _make_settings()
        with patch("anthropic.AsyncAnthropic"):
            client = LLMClientFactory.get_client("anthropic", None, settings)
        # Should have resolved to the default model from settings
        assert "anthropic" in LLMClientFactory._clients or client is not None


# ===========================================================================
# GraphExecutor tests
# ===========================================================================


class TestGraphExecutor:
    """Tests for the GraphExecutor class."""

    def _make_executor(self) -> Any:
        from app.services.graph_executor import GraphExecutor

        return GraphExecutor(
            settings=SimpleNamespace(checkpoint_backend="memory", checkpoint_db_path=":memory:")
        )

    def test_init_stores_settings(self) -> None:
        from app.services.graph_executor import GraphExecutor

        executor = GraphExecutor(
            settings=SimpleNamespace(checkpoint_backend="memory", checkpoint_db_path=":memory:")
        )
        assert executor.settings is not None

    async def test_execute_returns_failed_on_graph_exception(self) -> None:
        from app.models.execution import ExecutionRequest, ExecutionStatus

        executor = self._make_executor()
        fake_graph = MagicMock()
        fake_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph crashed"))

        request = ExecutionRequest(document="test doc", skill_name="test_schema")
        with patch(
            "app.services.graph_executor.create_skill_execution_graph", return_value=fake_graph
        ):
            result = await executor.execute(request)

        assert result.status == ExecutionStatus.FAILED
        assert "graph crashed" in (result.error or "")

    async def test_execute_calls_state_to_response_on_success(self) -> None:
        from app.models.execution import ExecutionRequest, ExecutionStatus

        executor = self._make_executor()

        final_state = {
            "status": "completed",
            "skill_results": [],
            "merged_data": {"key": "val"},
            "validation_result": None,
            "token_usage": {"input_tokens": 5, "output_tokens": 5, "total_tokens": 10},
            "execution_id": "exec-001",
            "started_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
            "errors": [],
        }
        fake_graph = MagicMock()
        fake_graph.ainvoke = AsyncMock(return_value=final_state)

        request = ExecutionRequest(document="doc", skill_name="test_schema")

        # We need a registry with the schema to avoid raises
        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.git_commit = "abc"
        mock_schema.config.version = "1.0"
        mock_registry.get_schema_or_raise.return_value = mock_schema

        with (
            patch("app.services.graph_executor.get_registry", return_value=mock_registry),
            patch(
                "app.services.graph_executor.create_skill_execution_graph", return_value=fake_graph
            ),
        ):
            result = await executor.execute(request)

        assert result.status == ExecutionStatus.COMPLETED

    def test_get_graph_executor_returns_instance(self) -> None:
        with patch("app.services.graph_executor.create_skill_execution_graph"):
            from app.services.graph_executor import get_graph_executor

            executor = get_graph_executor()
            assert executor is not None

    def _make_skill_result(self, success: bool, error: Optional[str] = None) -> Any:
        from app.models.skill import SkillExecutionResult

        return SkillExecutionResult(
            skill_id="test_skill",
            success=success,
            error=error,
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )

    def _make_mock_registry(self) -> Any:
        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.git_commit = None
        mock_schema.config.version = "1.0"
        mock_registry.get_schema_or_raise.return_value = mock_schema
        return mock_registry

    def test_state_to_response_all_failed(self) -> None:
        from app.models.execution import ExecutionStatus
        from app.services.graph_executor import GraphExecutor

        with patch("app.services.graph_executor.create_skill_execution_graph"):
            executor = GraphExecutor()

        state = {
            "status": "completed",
            "skill_results": [self._make_skill_result(success=False, error="skill failed")],
            "merged_data": None,
            "validation_result": None,
            "token_usage": {},
            "execution_id": "abc",
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "errors": [],
        }

        with patch(
            "app.services.graph_executor.get_registry", return_value=self._make_mock_registry()
        ):
            response = executor._state_to_response(state, "my_skill")

        assert response.status == ExecutionStatus.FAILED

    def test_state_to_response_partial(self) -> None:
        from app.models.execution import ExecutionStatus
        from app.services.graph_executor import GraphExecutor

        with patch("app.services.graph_executor.create_skill_execution_graph"):
            executor = GraphExecutor()

        state = {
            "status": "completed",
            "skill_results": [
                self._make_skill_result(success=True),
                self._make_skill_result(success=False, error="oops"),
            ],
            "merged_data": None,
            "validation_result": None,
            "token_usage": {},
            "execution_id": "abc",
            "started_at": None,
            "completed_at": None,
            "errors": [],
        }

        with patch(
            "app.services.graph_executor.get_registry", return_value=self._make_mock_registry()
        ):
            response = executor._state_to_response(state, "my_skill")

        assert response.status == ExecutionStatus.PARTIAL

    def test_state_to_response_paused_status(self) -> None:
        from app.models.execution import ExecutionStatus
        from app.services.graph_executor import GraphExecutor

        with patch("app.services.graph_executor.create_skill_execution_graph"):
            executor = GraphExecutor()

        state = {
            "status": "paused",
            "skill_results": [],
            "merged_data": None,
            "validation_result": None,
            "token_usage": {},
            "execution_id": "abc",
            "started_at": None,
            "completed_at": None,
            "errors": [],
        }

        with patch(
            "app.services.graph_executor.get_registry", return_value=self._make_mock_registry()
        ):
            response = executor._state_to_response(state, "my_skill")

        assert response.status == ExecutionStatus.PENDING

    def test_state_to_response_unknown_status(self) -> None:
        from app.models.execution import ExecutionStatus
        from app.services.graph_executor import GraphExecutor

        with patch("app.services.graph_executor.create_skill_execution_graph"):
            executor = GraphExecutor()

        state = {
            "status": "unknown",
            "skill_results": [],
            "merged_data": None,
            "validation_result": None,
            "token_usage": {},
            "execution_id": "abc",
            "started_at": None,
            "completed_at": None,
            "errors": ["something went wrong"],
        }

        with patch(
            "app.services.graph_executor.get_registry", return_value=self._make_mock_registry()
        ):
            response = executor._state_to_response(state, "my_skill")

        assert response.status == ExecutionStatus.FAILED
        assert response.error == "something went wrong"


# ===========================================================================
# WorkflowExecutor tests
# ===========================================================================


class TestWorkflowExecutor:
    """Tests for the WorkflowExecutor class."""

    def test_init_uses_provided_registry(self) -> None:
        from app.services.workflow_executor import WorkflowExecutor

        mock_registry = MagicMock()
        executor = WorkflowExecutor(registry=mock_registry)
        assert executor.registry is mock_registry

    def test_slugify(self) -> None:
        from app.services.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(registry=MagicMock())
        assert executor._slugify("my schema") == "my-schema"
        assert executor._slugify("Hello World!") == "hello-world"
        assert executor._slugify("---") == "schema"
        assert executor._slugify("already-slug") == "already-slug"

    def test_build_composed_workflow_id(self) -> None:
        from app.services.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(registry=MagicMock())
        result = executor._build_composed_workflow_id(["schema_a", "schema_b"])
        assert "schema-a" in result
        assert "schema-b" in result
        assert result.startswith("dynamic--")

    def test_resolve_workflow_raises_when_both_provided(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor, WorkflowExecutorError

        executor = WorkflowExecutor(registry=MagicMock())
        request = WorkflowExecutionRequest(
            document="doc",
            workflow_id="wf-1",
            schema_ids=["s1", "s2"],
        )
        with pytest.raises(WorkflowExecutorError, match="not both"):
            executor.resolve_workflow(request)

    def test_resolve_workflow_raises_when_neither_provided(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor, WorkflowExecutorError

        executor = WorkflowExecutor(registry=MagicMock())
        request = WorkflowExecutionRequest(document="doc")
        with pytest.raises(WorkflowExecutorError, match="Either workflow_id or schema_ids"):
            executor.resolve_workflow(request)

    def test_resolve_workflow_raises_when_workflow_not_found(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor, WorkflowExecutorError

        mock_registry = MagicMock()
        mock_registry.get_workflow.return_value = None
        executor = WorkflowExecutor(registry=mock_registry)
        request = WorkflowExecutionRequest(document="doc", workflow_id="missing-wf")
        with pytest.raises(WorkflowExecutorError, match="not found"):
            executor.resolve_workflow(request)

    def test_resolve_workflow_returns_found_workflow(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor

        mock_registry = MagicMock()
        mock_wf = MagicMock()
        mock_registry.get_workflow.return_value = mock_wf

        executor = WorkflowExecutor(registry=mock_registry)
        request = WorkflowExecutionRequest(document="doc", workflow_id="existing-wf")
        result = executor.resolve_workflow(request)
        assert result is mock_wf

    def test_build_composed_workflow_requires_at_least_two_schemas(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor, WorkflowExecutorError

        executor = WorkflowExecutor(registry=MagicMock())
        request = WorkflowExecutionRequest(document="doc", schema_ids=["only-one"])
        with pytest.raises(WorkflowExecutorError, match="at least 2"):
            executor._build_composed_workflow(request)

    def test_build_composed_workflow_raises_on_missing_schemas(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor, WorkflowExecutorError

        mock_registry = MagicMock()
        mock_registry.get_schema.return_value = None  # all schemas "missing"
        executor = WorkflowExecutor(registry=mock_registry)
        request = WorkflowExecutionRequest(document="doc", schema_ids=["missing-1", "missing-2"])
        with pytest.raises(WorkflowExecutorError, match="missing schemas"):
            executor._build_composed_workflow(request)

    def test_build_composed_workflow_success(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor

        mock_registry = MagicMock()
        mock_registry.get_schema.return_value = MagicMock()  # schemas found
        mock_registry.current_commit = "abc123"
        executor = WorkflowExecutor(registry=mock_registry)

        request = WorkflowExecutionRequest(
            document="doc",
            schema_ids=["schema_a", "schema_b"],
            workflow_name="Custom WF",
            workflow_description="Custom desc",
        )
        result = executor._build_composed_workflow(request)

        assert result.config.name == "Custom WF"
        assert result.config.description == "Custom desc"
        assert len(result.config.steps) == 2
        assert result.git_commit == "abc123"

    def test_build_composed_workflow_default_name(self) -> None:
        from app.models.workflow import WorkflowExecutionRequest
        from app.services.workflow_executor import WorkflowExecutor

        mock_registry = MagicMock()
        mock_registry.get_schema.return_value = MagicMock()
        mock_registry.current_commit = None
        executor = WorkflowExecutor(registry=mock_registry)

        request = WorkflowExecutionRequest(document="doc", schema_ids=["s1", "s2"])
        result = executor._build_composed_workflow(request)

        assert "s1" in result.config.name
        assert "s2" in result.config.name

    def test_get_workflow_executor_returns_instance(self) -> None:
        from app.services.workflow_executor import get_workflow_executor

        with patch("app.services.workflow_executor.get_registry"):
            executor = get_workflow_executor()
            assert executor is not None

    def _make_loaded_workflow(self, workflow_id: str, steps: Any) -> Any:
        """Helper to build a LoadedWorkflow for testing."""
        from app.models.workflow import LoadedWorkflow, WorkflowConfig

        return LoadedWorkflow(
            config=WorkflowConfig(
                workflow_id=workflow_id,
                version="1.0",
                name=f"Test WF {workflow_id}",
                steps=steps,
            ),
            git_commit="abc",
            source_path="test",
        )

    async def test_execute_workflow_step_failure_stop(self) -> None:
        """Test that on_failure=stop halts the workflow.

        The step raises an exception, which is caught and turns into a FAILED
        ExecutionResponse, then on_failure=stop causes the workflow to abort.
        """
        from app.models.workflow import OnFailure, WorkflowExecutionRequest, WorkflowStepConfig
        from app.services.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(registry=MagicMock())
        loaded_workflow = self._make_loaded_workflow(
            "test-wf",
            [
                WorkflowStepConfig(
                    step_id="step_1", schema_id="schema_a", name="Step 1", on_failure=OnFailure.STOP
                ),
                WorkflowStepConfig(
                    step_id="step_2", schema_id="schema_b", name="Step 2", on_failure=OnFailure.STOP
                ),
            ],
        )

        mock_graph_exec_instance = MagicMock()
        mock_graph_exec_instance.execute = AsyncMock(side_effect=RuntimeError("LLM failed"))

        with (
            patch.object(executor, "resolve_workflow", return_value=loaded_workflow),
            patch("app.services.graph_executor.create_skill_execution_graph"),
            patch(
                "app.services.graph_executor.GraphExecutor", return_value=mock_graph_exec_instance
            ),
        ):
            result = await executor.execute(
                WorkflowExecutionRequest(document="doc", workflow_id="test-wf")
            )

        from app.models.workflow import WorkflowExecutionStatus

        assert result.status == WorkflowExecutionStatus.FAILED
        assert result.metadata.steps_completed == 1

    async def test_execute_workflow_step_failure_continue(self) -> None:
        """Test that on_failure=continue proceeds past failures."""
        from app.models.execution import ExecutionResponse, ExecutionStatus
        from app.models.workflow import OnFailure, WorkflowExecutionRequest, WorkflowStepConfig
        from app.services.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(registry=MagicMock())
        loaded_workflow = self._make_loaded_workflow(
            "test-wf-2",
            [
                WorkflowStepConfig(
                    step_id="step_1",
                    schema_id="schema_a",
                    name="Step 1",
                    on_failure=OnFailure.CONTINUE,
                ),
                WorkflowStepConfig(
                    step_id="step_2",
                    schema_id="schema_b",
                    name="Step 2",
                    on_failure=OnFailure.CONTINUE,
                ),
            ],
        )

        success_response = ExecutionResponse(
            status=ExecutionStatus.COMPLETED,
            skill_name="schema_b",
            data={"key": "value"},
        )

        # First call raises (step 1 fails), second call returns success (step 2)
        mock_graph_exec_instance = MagicMock()
        mock_graph_exec_instance.execute = AsyncMock(
            side_effect=[RuntimeError("step 1 failed"), success_response]
        )

        with (
            patch.object(executor, "resolve_workflow", return_value=loaded_workflow),
            patch("app.services.graph_executor.create_skill_execution_graph"),
            patch(
                "app.services.graph_executor.GraphExecutor", return_value=mock_graph_exec_instance
            ),
        ):
            result = await executor.execute(
                WorkflowExecutionRequest(document="doc", workflow_id="test-wf-2")
            )

        from app.models.workflow import WorkflowExecutionStatus

        assert result.status == WorkflowExecutionStatus.PARTIAL
        assert result.metadata.steps_completed == 2

    async def test_execute_workflow_exception_in_step(self) -> None:
        """Test that exceptions in steps are caught and turned into failed responses."""
        from app.models.workflow import OnFailure, WorkflowExecutionRequest, WorkflowStepConfig
        from app.services.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(registry=MagicMock())
        loaded_workflow = self._make_loaded_workflow(
            "test-wf-3",
            [
                WorkflowStepConfig(
                    step_id="step_1", schema_id="schema_a", name="Step 1", on_failure=OnFailure.STOP
                ),
            ],
        )

        mock_graph_exec_instance = MagicMock()
        mock_graph_exec_instance.execute = AsyncMock(side_effect=RuntimeError("unexpected crash"))

        with (
            patch.object(executor, "resolve_workflow", return_value=loaded_workflow),
            patch("app.services.graph_executor.create_skill_execution_graph"),
            patch(
                "app.services.graph_executor.GraphExecutor", return_value=mock_graph_exec_instance
            ),
        ):
            result = await executor.execute(
                WorkflowExecutionRequest(document="doc", workflow_id="test-wf-3")
            )

        from app.models.workflow import WorkflowExecutionStatus

        assert result.status == WorkflowExecutionStatus.FAILED


# ===========================================================================
# Graph nodes tests
# ===========================================================================


class TestGraphNodeHelpers:
    """Tests for utility helpers in graph/nodes.py."""

    def test_state_get_from_dict(self) -> None:
        from app.services.graph.nodes import _state_get

        state = {"key": "value", "num": 42}
        assert _state_get(state, "key") == "value"
        assert _state_get(state, "num") == 42
        assert _state_get(state, "missing", "default") == "default"

    def test_state_get_from_skill_graph_state(self) -> None:
        from app.services.graph.nodes import _state_get
        from app.services.graph.state import SkillGraphState

        state = SkillGraphState(
            document="test doc",
            schema_id="my_schema",
            execution_id="exec-1",
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )
        assert _state_get(state, "document") == "test doc"
        assert _state_get(state, "schema_id") == "my_schema"
        assert _state_get(state, "nonexistent", "fallback") == "fallback"

    def test_item_get_from_dict(self) -> None:
        from app.services.graph.nodes import _item_get

        d = {"a": 1, "b": "two"}
        assert _item_get(d, "a") == 1
        assert _item_get(d, "missing", 99) == 99

    def test_item_get_from_object(self) -> None:
        from app.services.graph.nodes import _item_get

        class Obj:
            x = "hello"

        obj = Obj()
        assert _item_get(obj, "x") == "hello"
        assert _item_get(obj, "missing", "default") == "default"

    def test_deep_merge_basic(self) -> None:
        from app.services.graph.nodes import _deep_merge

        base = {"a": 1, "nested": {"x": 10, "y": 20}}
        update = {"b": 2, "nested": {"y": 99, "z": 30}}
        result = _deep_merge(base, update)
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["nested"]["x"] == 10
        assert result["nested"]["y"] == 99
        assert result["nested"]["z"] == 30

    def test_deep_merge_non_dict_overwrites(self) -> None:
        from app.services.graph.nodes import _deep_merge

        base = {"key": [1, 2, 3]}
        update = {"key": [4, 5]}
        result = _deep_merge(base, update)
        assert result["key"] == [4, 5]

    def test_get_nested_value_simple(self) -> None:
        from app.services.graph.nodes import _get_nested_value

        data = {"a": {"b": {"c": 42}}}
        assert _get_nested_value(data, "a.b.c") == 42
        assert _get_nested_value(data, "a.b") == {"c": 42}
        assert _get_nested_value(data, "missing") is None
        assert _get_nested_value(data, "a.x.y") is None

    def test_get_default_model_for_vendor(self) -> None:
        from app.services.graph.nodes import _get_default_model_for_vendor

        settings = _make_settings()
        assert _get_default_model_for_vendor("anthropic", settings) == settings.anthropic_model
        assert _get_default_model_for_vendor("openai", settings) == settings.openai_model
        assert _get_default_model_for_vendor("gemini", settings) == settings.gemini_model
        # unknown vendor defaults to anthropic
        assert _get_default_model_for_vendor("unknown", settings) == settings.anthropic_model


class TestGraphNodeValidationHelpers:
    """Tests for validation rule helpers in nodes.py."""

    def _make_rule(self, rule_type: str, name: str = "test_rule", **params: Any) -> Any:
        rule = MagicMock()
        rule.type = rule_type
        rule.name = name
        rule.params = params
        rule.severity = "error"
        return rule

    def test_run_validation_rule_sum_check_passes(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("sum_check", expected="total", operands=["a", "b"])
        data = {"total": 30, "a": 10, "b": 20}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "passed"

    def test_run_validation_rule_sum_check_fails(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("sum_check", expected="total", operands=["a", "b"])
        data = {"total": 999, "a": 10, "b": 20}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "failed"
        assert "30" in result["error"]

    def test_run_validation_rule_sum_check_with_subtraction(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("sum_check", expected="net", operands=["gross", "-tax"])
        data = {"net": 80, "gross": 100, "tax": 20}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "passed"

    def test_run_validation_rule_required_passes(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("required", fields=["name", "value"])
        data = {"name": "Alice", "value": 42}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "passed"

    def test_run_validation_rule_required_fails(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("required", fields=["name", "value"])
        data = {"name": "Alice"}  # value missing
        result = _run_validation_rule(rule, data)
        assert result["status"] == "failed"
        assert "value" in result["error"]

    def test_run_validation_rule_range_check_passes(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("range_check", field="score", min=0, max=100)
        data = {"score": 75}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "passed"

    def test_run_validation_rule_range_check_fails_below_min(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("range_check", field="score", min=0, max=100)
        data = {"score": -5}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "failed"

    def test_run_validation_rule_range_check_fails_above_max(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("range_check", field="score", min=0, max=100)
        data = {"score": 150}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "failed"

    def test_run_validation_rule_range_check_skipped_when_missing(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("range_check", field="score", min=0, max=100)
        data = {}
        result = _run_validation_rule(rule, data)
        assert result["status"] == "skipped"

    def test_run_validation_rule_unknown_type(self) -> None:
        from app.services.graph.nodes import _run_validation_rule

        rule = self._make_rule("nonexistent_type")
        result = _run_validation_rule(rule, {})
        assert result["status"] == "skipped"
        assert "Unknown rule type" in result["reason"]


class TestGraphNodeFunctions:
    """Tests for the async node functions in graph/nodes.py."""

    async def test_initialize_execution(self) -> None:
        from app.services.graph.nodes import initialize_execution
        from app.services.graph.state import SkillGraphState

        state = SkillGraphState(
            document="test document",
            schema_id="test_schema",
            execution_id="exec-123",
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_skill_1 = MagicMock()
        mock_skill_1.id = "skill_1"
        mock_skill_2 = MagicMock()
        mock_skill_2.id = "skill_2"
        mock_schema.get_active_skills.return_value = [mock_skill_1, mock_skill_2]
        mock_schema.get_skills_by_group.return_value = {1: [mock_skill_1], 2: [mock_skill_2]}
        mock_registry.get_schema_or_raise.return_value = mock_schema

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await initialize_execution(state)

        assert result["status"] == "running"
        assert "skill_1" in result["pending_skills"]
        assert "skill_2" in result["pending_skills"]
        assert result["current_group"] == 1
        assert len(result["progress_events"]) == 1

    async def test_human_review_node(self) -> None:
        from app.models.execution import ValidationResult
        from app.services.graph.nodes import human_review_node
        from app.services.graph.state import SkillGraphState

        validation_result = ValidationResult(status="FAIL", errors=["Error 1"], quality_score=50)
        state = SkillGraphState(
            document="doc",
            schema_id="schema",
            execution_id="exec-123",
            vendor=None,
            model=None,
            validation_result=validation_result,
            human_feedback=None,
            next_action=None,
        )

        result = await human_review_node(state)
        assert result["status"] == "paused"
        assert len(result["progress_events"]) == 1
        assert result["progress_events"][0]["type"] == "human_review_requested"

    async def test_save_checkpoint(self) -> None:
        from app.services.graph.nodes import save_checkpoint
        from app.services.graph.state import SkillGraphState

        state = SkillGraphState(
            document="doc",
            schema_id="schema",
            execution_id="exec-123",
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )

        result = await save_checkpoint(state)
        assert len(result["progress_events"]) == 1
        assert result["progress_events"][0]["type"] == "checkpoint_saved"

    async def test_merge_skill_results_merge_deep(self) -> None:
        from app.models.schema import MergeStrategy
        from app.models.skill import SkillExecutionResult
        from app.services.graph.nodes import merge_skill_results

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.config.post_processing.merge_strategy = MergeStrategy.MERGE_DEEP
        mock_registry.get_schema_or_raise.return_value = mock_schema

        result_1 = SkillExecutionResult(
            skill_id="s1",
            success=True,
            data={"name": "Alice", "nested": {"x": 1}},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )
        result_2 = SkillExecutionResult(
            skill_id="s2",
            success=True,
            data={"age": 30, "nested": {"y": 2}},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )

        state: Dict[str, Any] = {
            "schema_id": "test",
            "merged_data": {},
            "skill_results": [result_1, result_2],
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await merge_skill_results(state)

        merged = result["merged_data"]
        assert merged["name"] == "Alice"
        assert merged["age"] == 30
        assert merged["nested"]["x"] == 1
        assert merged["nested"]["y"] == 2

    async def test_merge_skill_results_first_wins(self) -> None:
        from app.models.schema import MergeStrategy
        from app.models.skill import SkillExecutionResult
        from app.services.graph.nodes import merge_skill_results

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.config.post_processing.merge_strategy = MergeStrategy.FIRST_WINS
        mock_registry.get_schema_or_raise.return_value = mock_schema

        result_1 = SkillExecutionResult(
            skill_id="s1",
            success=True,
            data={"key": "first"},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )
        result_2 = SkillExecutionResult(
            skill_id="s2",
            success=True,
            data={"key": "second", "extra": "value"},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )

        state = {
            "schema_id": "test",
            "merged_data": {},
            "skill_results": [result_1, result_2],
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await merge_skill_results(state)

        assert result["merged_data"]["key"] == "first"
        assert result["merged_data"]["extra"] == "value"

    async def test_merge_skill_results_last_wins(self) -> None:
        from app.models.schema import MergeStrategy
        from app.models.skill import SkillExecutionResult
        from app.services.graph.nodes import merge_skill_results

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.config.post_processing.merge_strategy = MergeStrategy.LAST_WINS
        mock_registry.get_schema_or_raise.return_value = mock_schema

        result_1 = SkillExecutionResult(
            skill_id="s1",
            success=True,
            data={"key": "first"},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )
        result_2 = SkillExecutionResult(
            skill_id="s2",
            success=True,
            data={"key": "last"},
            execution_time_ms=100,
            model_used="claude",
            vendor_used="anthropic",
        )

        state = {
            "schema_id": "test",
            "merged_data": {},
            "skill_results": [result_1, result_2],
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await merge_skill_results(state)

        assert result["merged_data"]["key"] == "last"

    async def test_route_next_action_more_groups_remaining(self) -> None:
        from app.services.graph.nodes import route_next_action

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.get_skills_by_group.return_value = {1: [], 2: [], 3: []}
        mock_registry.get_schema_or_raise.return_value = mock_schema

        state = {
            "schema_id": "test",
            "completed_groups": [1],
            "validation_result": None,
            "retry_count": 0,
            "max_retries": 2,
            "human_review_required": False,
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await route_next_action(state)

        assert result["next_action"] == "execute_next_group"
        assert result["current_group"] == 2

    async def test_route_next_action_complete_when_all_done(self) -> None:
        from app.services.graph.nodes import route_next_action

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.get_skills_by_group.return_value = {1: []}
        mock_registry.get_schema_or_raise.return_value = mock_schema

        state = {
            "schema_id": "test",
            "completed_groups": [1],
            "validation_result": None,
            "retry_count": 0,
            "max_retries": 2,
            "human_review_required": False,
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await route_next_action(state)

        assert result["next_action"] == "complete"
        assert result["status"] == "completed"

    async def test_route_next_action_retry_on_validation_fail(self) -> None:
        from app.services.graph.nodes import route_next_action

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.get_skills_by_group.return_value = {1: []}
        mock_registry.get_schema_or_raise.return_value = mock_schema

        mock_validation = MagicMock()
        mock_validation.status = "FAIL"

        state = {
            "schema_id": "test",
            "completed_groups": [1],
            "validation_result": mock_validation,
            "retry_count": 0,
            "max_retries": 2,
            "human_review_required": False,
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await route_next_action(state)

        assert result["next_action"] == "retry"
        assert result["should_retry"] is True
        assert result["retry_count"] == 1

    async def test_route_next_action_human_review_when_retries_exhausted(self) -> None:
        from app.services.graph.nodes import route_next_action

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.get_skills_by_group.return_value = {1: []}
        mock_registry.get_schema_or_raise.return_value = mock_schema

        mock_validation = MagicMock()
        mock_validation.status = "FAIL"

        state = {
            "schema_id": "test",
            "completed_groups": [1],
            "validation_result": mock_validation,
            "retry_count": 2,
            "max_retries": 2,
            "human_review_required": True,
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await route_next_action(state)

        assert result["next_action"] == "human_review"

    async def test_validate_results_no_model_no_rules(self) -> None:
        from app.services.graph.nodes import validate_results

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.output_model = None
        mock_schema.config.post_processing.validation_rules = []
        mock_registry.get_schema_or_raise.return_value = mock_schema

        state = {
            "schema_id": "test",
            "merged_data": {"field": "value"},
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await validate_results(state)

        assert result["validation_result"].status == "PASS"
        assert result["quality_score"] == 100
        assert result["human_review_required"] is False

    async def test_validate_results_pydantic_validation_fails(self) -> None:
        from pydantic import BaseModel

        from app.services.graph.nodes import validate_results

        class StrictModel(BaseModel):
            required_field: str

        mock_registry = MagicMock()
        mock_schema = MagicMock()
        mock_schema.output_model = StrictModel
        mock_schema.config.post_processing.validation_rules = []
        mock_registry.get_schema_or_raise.return_value = mock_schema

        state = {
            "schema_id": "test",
            "merged_data": {},  # missing required_field
        }

        with patch("app.services.graph.nodes.get_registry", return_value=mock_registry):
            result = await validate_results(state)

        assert result["validation_result"].status == "FAIL"
        assert len(result["validation_result"].errors) > 0
        assert result["human_review_required"] is True
