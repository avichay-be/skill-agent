"""Regression tests for recently fixed execution and webhook behavior."""

import inspect
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from starlette.requests import Request

from app.api.routes import webhooks
from app.api.routes.execute import execute_extraction_from_file
from app.models.execution import (
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
)
from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
from app.models.skill import Skill, SkillConfig
from app.services.graph.builder import create_skill_execution_graph
from app.services.graph.state import SkillGraphState


def _build_execution_response() -> ExecutionResponse:
    return ExecutionResponse(
        status=ExecutionStatus.COMPLETED,
        skill_name="test_schema",
        data={"field": "value"},
        metadata=ExecutionMetadata(
            token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        ),
    )


def _build_schema() -> LoadedSchema:
    skill_1 = Skill(
        id="skill_1",
        name="Skill 1",
        prompt="Prompt for skill 1",
        config=SkillConfig(
            id="skill_1",
            name="Skill 1",
            prompt_file="prompts/skill_1.md",
            parallel_group=1,
        ),
        schema_id="test_schema",
        version="1.0.0",
        file_path="/tmp/skill_1.md",
    )
    skill_2 = Skill(
        id="skill_2",
        name="Skill 2",
        prompt="Prompt for skill 2",
        config=SkillConfig(
            id="skill_2",
            name="Skill 2",
            prompt_file="prompts/skill_2.md",
            parallel_group=2,
        ),
        schema_id="test_schema",
        version="1.0.0",
        file_path="/tmp/skill_2.md",
    )
    return LoadedSchema(
        config=SchemaConfig(
            schema_id="test_schema",
            version="1.0.0",
            name="Test Schema",
            post_processing=PostProcessing(),
        ),
        skills={skill_1.id: skill_1, skill_2.id: skill_2},
        git_commit="abc123",
        source_path="/tmp/test_schema",
    )


class TestFileExecutionRoute:
    """Tests for executor selection in file uploads."""

    @pytest.mark.asyncio
    async def test_file_upload_uses_graph_executor_when_enabled(self) -> None:
        registry = MagicMock()
        registry.get_schema.return_value = object()
        settings = MagicMock()
        settings.allowed_file_extensions = [".txt"]
        settings.max_upload_size_mb = 10
        settings.use_langgraph = True

        graph_executor = AsyncMock()
        graph_executor.execute = AsyncMock(return_value=_build_execution_response())

        file = UploadFile(file=io.BytesIO(b"hello world"), filename="document.txt")
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with (
            patch("app.api.routes.execute.get_settings", return_value=settings),
            patch("app.api.routes.execute.get_graph_executor", return_value=graph_executor),
            patch("app.api.routes.execute.get_executor") as get_executor,
            patch("app.api.routes.execute.get_cosmosdb_service", return_value=None),
        ):
            response = await execute_extraction_from_file(
                request=request,
                file=file,
                skill_name="test_schema",
                vendor=None,
                model=None,
                save_to_cosmos=False,
                _api_key="test-key",
                registry=registry,
            )

        assert response.status == ExecutionStatus.COMPLETED
        graph_executor.execute.assert_awaited_once()
        get_executor.assert_not_called()

        exec_request = graph_executor.execute.await_args.args[0]
        assert isinstance(exec_request, ExecutionRequest)
        assert exec_request.document == "hello world"

    @pytest.mark.asyncio
    async def test_file_upload_uses_legacy_executor_when_langgraph_disabled(self) -> None:
        registry = MagicMock()
        registry.get_schema.return_value = object()
        settings = MagicMock()
        settings.allowed_file_extensions = [".txt"]
        settings.max_upload_size_mb = 10
        settings.use_langgraph = False

        legacy_executor = AsyncMock()
        legacy_executor.execute = AsyncMock(return_value=_build_execution_response())

        file = UploadFile(file=io.BytesIO(b"hello world"), filename="document.txt")
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with (
            patch("app.api.routes.execute.get_settings", return_value=settings),
            patch("app.api.routes.execute.get_executor", return_value=legacy_executor),
            patch("app.api.routes.execute.get_graph_executor") as get_graph_executor,
            patch("app.api.routes.execute.get_cosmosdb_service", return_value=None),
        ):
            response = await execute_extraction_from_file(
                request=request,
                file=file,
                skill_name="test_schema",
                vendor=None,
                model=None,
                save_to_cosmos=False,
                _api_key="test-key",
                registry=registry,
            )

        assert response.status == ExecutionStatus.COMPLETED
        legacy_executor.execute.assert_awaited_once()
        get_graph_executor.assert_not_called()


class TestWebhookReloadRoute:
    """Tests for webhook reload protection."""

    def test_force_reload_route_declares_api_key_dependency(self) -> None:
        route = next(
            route
            for route in webhooks.router.routes
            if getattr(route, "endpoint", None) is webhooks.force_reload
        )

        dependency_names = {dependency.name for dependency in route.dependant.dependencies}

        assert "_api_key" in dependency_names
        assert "_api_key" in inspect.signature(webhooks.force_reload).parameters


class TestLangGraphExecution:
    """Tests for graph state accumulation across parallel groups."""

    @pytest.mark.asyncio
    async def test_graph_accumulates_completed_groups(self) -> None:
        registry = MagicMock()
        registry.get_schema_or_raise.return_value = _build_schema()

        client = MagicMock()
        client.extract_json = AsyncMock(
            side_effect=[
                (
                    {"field_1": "value_1"},
                    TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                ),
                (
                    {"field_2": "value_2"},
                    TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
                ),
            ]
        )

        graph = create_skill_execution_graph(checkpointer_type="memory")
        initial_state = SkillGraphState(
            document="test document",
            schema_id="test_schema",
            execution_id="exec-123",
        ).model_dump()

        with (
            patch("app.services.graph.nodes.get_registry", return_value=registry),
            patch("app.services.graph.nodes.LLMClientFactory.get_client", return_value=client),
        ):
            final_state: dict[str, Any] = await graph.ainvoke(
                initial_state, config={"configurable": {"thread_id": "exec-123"}}
            )

        assert final_state["status"] == "completed"
        assert final_state["completed_groups"] == [1, 2]
        assert final_state["merged_data"] == {"field_1": "value_1", "field_2": "value_2"}
        assert client.extract_json.await_count == 2
