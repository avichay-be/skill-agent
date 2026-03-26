"""Regression tests for recently fixed execution and webhook behavior."""

import inspect
import io
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.routing import APIRoute
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from starlette.requests import Request

from app.api.file_uploads import read_uploaded_text_file
from app.api.routes import webhooks
from app.api.routes.execute import execute_extraction_from_file
from app.api.routes.workflows import execute_workflow, execute_workflow_from_file
from app.models.execution import (
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
)
from app.models.schema import LoadedSchema, PostProcessing, SchemaConfig
from app.models.skill import Skill, SkillConfig
from app.models.workflow import (
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionStatus,
)
from app.services.graph.builder import create_skill_execution_graph
from app.services.graph.state import SkillGraphState
from app.services.graph_executor import GraphExecutor


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
    """Tests for file uploads using the graph executor."""

    @pytest.mark.asyncio
    async def test_file_upload_uses_graph_executor(self) -> None:
        registry = MagicMock()
        registry.get_schema.return_value = object()
        settings = MagicMock()
        settings.allowed_file_extensions = [".txt"]
        settings.max_upload_size_mb = 10

        graph_executor = AsyncMock()
        graph_executor.execute = AsyncMock(return_value=_build_execution_response())

        file = UploadFile(file=io.BytesIO(b"hello world"), filename="document.txt")
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with (
            patch("app.api.routes.execute.get_settings", return_value=settings),
            patch("app.api.routes.execute.get_graph_executor", return_value=graph_executor),
        ):
            response = await execute_extraction_from_file(
                request=request,
                file=file,
                skill_name="test_schema",
                vendor=None,
                model=None,
                _api_key="test-key",
                registry=registry,
            )

        assert response.status == ExecutionStatus.COMPLETED
        graph_executor.execute.assert_awaited_once()

        exec_request = graph_executor.execute.await_args.args[0]
        assert isinstance(exec_request, ExecutionRequest)
        assert exec_request.document == "hello world"
        assert exec_request.save_to_cosmos is False


class TestWorkflowFileExecutionRoute:
    """Tests for multipart workflow execution."""

    @pytest.mark.asyncio
    async def test_workflow_file_upload_builds_workflow_request(self) -> None:
        registry = MagicMock()
        loaded_workflow = MagicMock()
        loaded_workflow.config.steps = [MagicMock(schema_id="test_schema")]
        registry.get_workflow.return_value = loaded_workflow
        registry.get_schema.return_value = object()

        executor = AsyncMock()
        executor.execute = AsyncMock(
            return_value=WorkflowExecutionResponse(
                status=WorkflowExecutionStatus.COMPLETED,
                workflow_id="test_workflow",
                workflow_name="Test Workflow",
            )
        )
        settings = MagicMock()
        settings.allowed_file_extensions = [".txt"]
        settings.max_upload_size_mb = 10

        file = UploadFile(file=io.BytesIO(b"workflow input"), filename="document.txt")
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with (
            patch("app.api.routes.workflows.get_settings", return_value=settings),
        ):
            response = await execute_workflow_from_file(
                request=request,
                file=file,
                workflow_id="test_workflow",
                vendor="openai",
                model="gpt-4o",
                _api_key="test-key",
                registry=registry,
                executor=executor,
            )

        assert response.status == WorkflowExecutionStatus.COMPLETED
        executor.execute.assert_awaited_once()

        workflow_request = executor.execute.await_args.args[0]
        assert workflow_request.document == "workflow input"
        assert workflow_request.workflow_id == "test_workflow"
        assert workflow_request.vendor == "openai"
        assert workflow_request.model == "gpt-4o"
        assert workflow_request.save_to_cosmos is False

    @pytest.mark.asyncio
    async def test_workflow_file_upload_supports_dynamic_schema_sequence(self) -> None:
        registry = MagicMock()
        registry.get_schema.return_value = object()

        executor = AsyncMock()
        executor.execute = AsyncMock(
            return_value=WorkflowExecutionResponse(
                status=WorkflowExecutionStatus.COMPLETED,
                workflow_id="dynamic--test-schema--test-schema",
                workflow_name="Dynamic Workflow",
            )
        )
        settings = MagicMock()
        settings.allowed_file_extensions = [".txt"]
        settings.max_upload_size_mb = 10

        file = UploadFile(file=io.BytesIO(b"workflow input"), filename="document.txt")
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with (
            patch("app.api.routes.workflows.get_settings", return_value=settings),
        ):
            response = await execute_workflow_from_file(
                request=request,
                file=file,
                workflow_id=None,
                schema_ids=["test_schema", "test_schema"],
                workflow_name="Dynamic Workflow",
                workflow_description="Generated on demand",
                vendor="openai",
                model="gpt-4o",
                _api_key="test-key",
                registry=registry,
                executor=executor,
            )

        assert response.status == WorkflowExecutionStatus.COMPLETED
        executor.execute.assert_awaited_once()

        workflow_request = executor.execute.await_args.args[0]
        assert workflow_request.document == "workflow input"
        assert workflow_request.workflow_id is None
        assert workflow_request.schema_ids == ["test_schema", "test_schema"]
        assert workflow_request.workflow_name == "Dynamic Workflow"
        assert workflow_request.workflow_description == "Generated on demand"
        assert workflow_request.save_to_cosmos is False

    @pytest.mark.asyncio
    async def test_execute_workflow_rejects_both_workflow_id_and_schema_ids(self) -> None:
        registry = MagicMock()
        executor = AsyncMock()
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

        with pytest.raises(HTTPException) as exc_info:
            await execute_workflow(
                request=request,
                workflow_request=WorkflowExecutionRequest(
                    document="doc",
                    workflow_id="saved_workflow",
                    schema_ids=["test_schema", "test_schema"],
                    save_to_cosmos=False,
                ),
                _api_key="test-key",
                registry=registry,
                executor=executor,
            )

        assert exc_info.value.status_code == 400
        assert "either workflow_id or schema_ids" in exc_info.value.detail


class TestSharedFileUploadHelper:
    """Tests for shared multipart file handling."""

    @pytest.mark.asyncio
    async def test_read_uploaded_text_file_rejects_disallowed_extension(self) -> None:
        file = UploadFile(file=io.BytesIO(b"test"), filename="malware.exe")

        with pytest.raises(HTTPException) as exc_info:
            await read_uploaded_text_file(
                file,
                allowed_file_extensions=[".txt"],
                max_upload_size_mb=10,
            )

        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_read_uploaded_text_file_rejects_oversized_file(self) -> None:
        file = UploadFile(file=io.BytesIO(b"12345"), filename="document.txt")

        with pytest.raises(HTTPException) as exc_info:
            await read_uploaded_text_file(
                file,
                allowed_file_extensions=[".txt"],
                max_upload_size_mb=0,
            )

        assert exc_info.value.status_code == 413


class TestWebhookReloadRoute:
    """Tests for webhook reload protection."""

    def test_force_reload_route_declares_api_key_dependency(self) -> None:
        route = next(
            route
            for route in webhooks.router.routes
            if isinstance(route, APIRoute)
            and getattr(route, "endpoint", None) is webhooks.force_reload
        )
        route = cast(APIRoute, route)

        dependency_names = {dependency.name for dependency in route.dependant.dependencies}

        assert "_api_key" in dependency_names
        assert "_api_key" in inspect.signature(webhooks.force_reload).parameters


class TestCheckpointDirAutoCreate:
    """Tests for auto-creating SQLite checkpoint directory."""

    @pytest.mark.asyncio
    async def test_graph_executor_creates_checkpoint_dir(self, tmp_path: Any) -> None:
        """GraphExecutor should auto-create the checkpoint directory."""
        db_path = tmp_path / "subdir" / "nested" / "checkpoints.db"
        executor = GraphExecutor(
            settings=SimpleNamespace(
                checkpoint_backend="sqlite",
                checkpoint_db_path=str(db_path),
            )
        )
        # Should not raise FileNotFoundError
        async with executor._checkpointer_context() as cp:
            assert cp is not None
        assert db_path.parent.exists()


class TestLangGraphExecution:
    """Tests for graph state accumulation across parallel groups."""

    def test_graph_requires_live_sqlite_checkpointer(self) -> None:
        with pytest.raises(ValueError, match="live saver instance"):
            create_skill_execution_graph(checkpointer_type="sqlite")

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
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        ).model_dump()

        with (
            patch("app.services.graph.nodes.get_registry", return_value=registry),
            patch("app.services.execution_utils.LLMClientFactory.get_client", return_value=client),
        ):
            final_state: dict[str, Any] = await graph.ainvoke(
                initial_state, config={"configurable": {"thread_id": "exec-123"}}
            )

        assert final_state["status"] == "completed"
        assert final_state["completed_groups"] == [1, 2]
        assert final_state["merged_data"] == {"field_1": "value_1", "field_2": "value_2"}
        assert client.extract_json.await_count == 2

    @pytest.mark.asyncio
    async def test_graph_executor_executes_with_sqlite_checkpointer(self) -> None:
        registry = MagicMock()
        registry.get_schema_or_raise.return_value = _build_schema()

        executor = GraphExecutor(
            settings=SimpleNamespace(checkpoint_backend="sqlite", checkpoint_db_path=":memory:")
        )
        request = ExecutionRequest(document="test document", skill_name="test_schema")
        captured_checkpointer: AsyncSqliteSaver | None = None

        fake_graph = MagicMock()
        fake_graph.ainvoke = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": "exec-123",
                "merged_data": {"field_1": "value_1", "field_2": "value_2"},
                "skill_results": [],
            }
        )

        def fake_create_skill_execution_graph(*args: Any, **kwargs: Any) -> Any:
            nonlocal captured_checkpointer
            checkpointer = kwargs["checkpointer"]
            assert isinstance(checkpointer, AsyncSqliteSaver)
            assert hasattr(checkpointer, "get_next_version")
            captured_checkpointer = checkpointer
            return fake_graph

        with (
            patch("app.services.graph_executor.get_registry", return_value=registry),
            patch(
                "app.services.graph_executor.create_skill_execution_graph",
                side_effect=fake_create_skill_execution_graph,
            ),
        ):
            response = await executor.execute(request)

        assert response.status == ExecutionStatus.COMPLETED
        assert response.data == {"field_1": "value_1", "field_2": "value_2"}
        assert captured_checkpointer is not None
        fake_graph.ainvoke.assert_awaited_once()
