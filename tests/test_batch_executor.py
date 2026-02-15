"""Tests for Anthropic Batch API integration."""

import os
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.execution import (
    BatchExecutionRequest,
    BatchExecutionResponse,
    BatchStatus,
    DocumentItem,
    ExecutionStatus,
    TokenUsage,
)
from app.services.batch_executor import BatchExecutor, BatchExecutorError
from app.services.llm_client import AnthropicClient, LLMClientError


# ---------------------------------------------------------------------------
# AnthropicClient batch method tests
# ---------------------------------------------------------------------------
class TestAnthropicClientBatch:
    """Tests for AnthropicClient batch methods."""

    @pytest.fixture
    def mock_anthropic_client(self) -> AnthropicClient:
        """Create an AnthropicClient with a mocked SDK client."""
        with patch("anthropic.AsyncAnthropic"):
            client = AnthropicClient(api_key="test-key", model="claude-sonnet-4-20250514")
        client.client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_create_batch_success(self, mock_anthropic_client: AnthropicClient) -> None:
        """Test successful batch creation."""
        mock_batch = MagicMock()
        mock_batch.id = "batch_abc123"
        mock_anthropic_client.client.messages.batches.create = AsyncMock(return_value=mock_batch)

        requests = [
            ("doc1|skill1", "Extract data", "Document content", 0.0, 4096),
        ]
        batch_id = await mock_anthropic_client.create_batch(requests)

        assert batch_id == "batch_abc123"
        mock_anthropic_client.client.messages.batches.create.assert_called_once()
        call_kwargs = mock_anthropic_client.client.messages.batches.create.call_args
        batch_requests = call_kwargs.kwargs["requests"]
        assert len(batch_requests) == 1
        assert batch_requests[0]["custom_id"] == "doc1|skill1"
        assert batch_requests[0]["params"]["model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_create_batch_api_error(self, mock_anthropic_client: AnthropicClient) -> None:
        """Test batch creation failure."""
        mock_anthropic_client.client.messages.batches.create = AsyncMock(
            side_effect=Exception("API down")
        )

        with pytest.raises(LLMClientError, match="Anthropic Batch API error"):
            await mock_anthropic_client.create_batch(
                [
                    ("id1", "prompt", "doc", 0.0, 4096),
                ]
            )

    @pytest.mark.asyncio
    async def test_get_batch_status_success(self, mock_anthropic_client: AnthropicClient) -> None:
        """Test retrieving batch status."""
        mock_batch = MagicMock()
        mock_batch.processing_status = "in_progress"
        mock_batch.request_counts.processing = 3
        mock_batch.request_counts.succeeded = 0
        mock_batch.request_counts.errored = 0
        mock_batch.request_counts.canceled = 0
        mock_batch.request_counts.expired = 0
        mock_batch.ended_at = None
        mock_batch.created_at = "2025-01-01T00:00:00Z"

        mock_anthropic_client.client.messages.batches.retrieve = AsyncMock(return_value=mock_batch)

        result = await mock_anthropic_client.get_batch_status("batch_abc123")

        assert result["processing_status"] == "in_progress"
        assert result["request_counts"]["processing"] == 3
        assert result["request_counts"]["succeeded"] == 0

    @pytest.mark.asyncio
    async def test_get_batch_results_success(self, mock_anthropic_client: AnthropicClient) -> None:
        """Test retrieving batch results."""
        # Build mock entries
        mock_entry_1 = MagicMock()
        mock_entry_1.custom_id = "doc1|skill1"
        mock_entry_1.result.type = "succeeded"
        mock_entry_1.result.message.content = [MagicMock(text='{"field1": "value1"}')]
        mock_entry_1.result.message.usage.input_tokens = 100
        mock_entry_1.result.message.usage.output_tokens = 50

        mock_entry_2 = MagicMock()
        mock_entry_2.custom_id = "doc1|skill2"
        mock_entry_2.result.type = "errored"

        async def mock_results_iter(batch_id: str) -> AsyncMock:
            """Return an async iterable of results."""

            class _AsyncIter:
                def __init__(self) -> None:
                    self._items = [mock_entry_1, mock_entry_2]
                    self._idx = 0

                def __aiter__(self) -> "_AsyncIter":
                    return self

                async def __anext__(self) -> MagicMock:
                    if self._idx >= len(self._items):
                        raise StopAsyncIteration
                    item = self._items[self._idx]
                    self._idx += 1
                    return item

            return _AsyncIter()

        mock_anthropic_client.client.messages.batches.results = mock_results_iter

        results = await mock_anthropic_client.get_batch_results("batch_abc123")

        assert "doc1|skill1" in results
        text, usage = results["doc1|skill1"]
        assert text == '{"field1": "value1"}'
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

        # Errored entry should have empty text
        assert "doc1|skill2" in results
        text2, usage2 = results["doc1|skill2"]
        assert text2 == ""
        assert usage2.total_tokens == 0


# ---------------------------------------------------------------------------
# BatchExecutor tests
# ---------------------------------------------------------------------------
class TestBatchExecutor:
    """Tests for BatchExecutor service."""

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        """Create mock registry."""
        from app.models.skill import Skill, SkillConfig

        skill1 = Skill(
            id="skill_1",
            name="Test Skill 1",
            prompt="Extract field1",
            config=SkillConfig(
                id="skill_1",
                name="Test Skill 1",
                prompt_file="prompts/skill_1.md",
                parallel_group=1,
            ),
            schema_id="test_schema",
            version="abc123",
            file_path="prompts/skill_1.md",
        )

        schema = MagicMock()
        schema.get_active_skills.return_value = [skill1]
        schema.config.version = "1.0.0"
        schema.git_commit = "abc123"

        registry = MagicMock()
        registry.get_schema.return_value = schema
        registry.get_schema_or_raise.return_value = schema
        return registry

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.enable_batch_api = True
        settings.batch_poll_interval_seconds = 30
        settings.anthropic_api_key = "test-key"
        settings.anthropic_model = "claude-sonnet-4-20250514"
        settings.default_vendor = "anthropic"
        return settings

    @pytest.fixture
    def mock_anthropic_client(self) -> AsyncMock:
        """Create a mock Anthropic client."""
        client = AsyncMock(spec=AnthropicClient)
        client.create_batch = AsyncMock(return_value="batch_test123")
        client._extract_json_from_text = MagicMock(return_value={"field1": "value1"})
        return client

    @pytest.mark.asyncio
    async def test_submit_batch_success(
        self, mock_registry: MagicMock, mock_settings: MagicMock, mock_anthropic_client: AsyncMock
    ) -> None:
        """Test successful batch submission."""
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        with patch.object(executor, "_get_anthropic_client", return_value=mock_anthropic_client):
            request = BatchExecutionRequest(
                documents=[
                    DocumentItem(id="doc1", content="Document 1 content"),
                    DocumentItem(id="doc2", content="Document 2 content"),
                ],
                skill_name="test_schema",
            )

            response = await executor.submit_batch(request)

        assert response.batch_id == "batch_test123"
        assert response.status == BatchStatus.SUBMITTED
        assert response.total_documents == 2

        # Verify batch request was called with correct data
        mock_anthropic_client.create_batch.assert_called_once()
        call_args = mock_anthropic_client.create_batch.call_args[0][0]
        assert len(call_args) == 2  # 2 docs × 1 skill

    @pytest.mark.asyncio
    async def test_submit_batch_non_anthropic_vendor(
        self, mock_registry: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test batch submission with non-anthropic vendor fails."""
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        request = BatchExecutionRequest(
            documents=[DocumentItem(id="doc1", content="content")],
            skill_name="test_schema",
            vendor="openai",
        )

        with pytest.raises(BatchExecutorError, match="only supported with Anthropic"):
            await executor.submit_batch(request)

    @pytest.mark.asyncio
    async def test_submit_batch_no_active_skills(
        self, mock_registry: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test batch submission with no active skills fails."""
        mock_registry.get_schema_or_raise.return_value.get_active_skills.return_value = []
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        request = BatchExecutionRequest(
            documents=[DocumentItem(id="doc1", content="content")],
            skill_name="test_schema",
        )

        with pytest.raises(BatchExecutorError, match="No active skills"):
            await executor.submit_batch(request)

    @pytest.mark.asyncio
    async def test_get_batch_status_processing(
        self, mock_registry: MagicMock, mock_settings: MagicMock, mock_anthropic_client: AsyncMock
    ) -> None:
        """Test getting status of a processing batch."""
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        # First submit a batch
        with patch.object(executor, "_get_anthropic_client", return_value=mock_anthropic_client):
            request = BatchExecutionRequest(
                documents=[DocumentItem(id="doc1", content="content")],
                skill_name="test_schema",
            )
            submit_response = await executor.submit_batch(request)

        # Now check status
        mock_anthropic_client.get_batch_status = AsyncMock(
            return_value={
                "processing_status": "in_progress",
                "request_counts": {
                    "processing": 1,
                    "succeeded": 0,
                    "errored": 0,
                    "canceled": 0,
                    "expired": 0,
                },
                "ended_at": None,
                "created_at": "2025-01-01T00:00:00Z",
            }
        )

        with patch.object(executor, "_get_anthropic_client", return_value=mock_anthropic_client):
            status_response = await executor.get_batch_status(submit_response.batch_id)

        assert status_response.status == BatchStatus.PROCESSING
        assert status_response.results is None

    @pytest.mark.asyncio
    async def test_get_batch_status_completed(
        self, mock_registry: MagicMock, mock_settings: MagicMock, mock_anthropic_client: AsyncMock
    ) -> None:
        """Test getting status of a completed batch with results."""
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        # First submit a batch
        with patch.object(executor, "_get_anthropic_client", return_value=mock_anthropic_client):
            request = BatchExecutionRequest(
                documents=[DocumentItem(id="doc1", content="content")],
                skill_name="test_schema",
            )
            submit_response = await executor.submit_batch(request)

        # Mock completed status
        mock_anthropic_client.get_batch_status = AsyncMock(
            return_value={
                "processing_status": "ended",
                "request_counts": {
                    "processing": 0,
                    "succeeded": 1,
                    "errored": 0,
                    "canceled": 0,
                    "expired": 0,
                },
                "ended_at": "2025-01-01T01:00:00Z",
                "created_at": "2025-01-01T00:00:00Z",
            }
        )

        # Mock results
        mock_anthropic_client.get_batch_results = AsyncMock(
            return_value={
                "doc1|skill_1": (
                    '{"field1": "extracted_value"}',
                    TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                ),
            }
        )

        with patch.object(executor, "_get_anthropic_client", return_value=mock_anthropic_client):
            status_response = await executor.get_batch_status(submit_response.batch_id)

        assert status_response.status == BatchStatus.COMPLETED
        assert status_response.results is not None
        assert "doc1" in status_response.results
        assert status_response.results["doc1"].status == ExecutionStatus.COMPLETED
        assert status_response.results["doc1"].data == {"field1": "value1"}

    @pytest.mark.asyncio
    async def test_get_batch_status_unknown_id(
        self, mock_registry: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test getting status of an unknown batch ID."""
        executor = BatchExecutor(registry=mock_registry, settings=mock_settings)

        with pytest.raises(BatchExecutorError, match="Unknown batch ID"):
            await executor.get_batch_status("nonexistent_batch")


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------
class TestBatchEndpoints:
    """Tests for batch API endpoints."""

    @pytest.fixture
    def batch_app_client(self, temp_skills_dir: Path) -> Generator[TestClient, None, None]:
        """Create test client with batch API enabled."""
        from app.services.skill_registry import SkillRegistry

        SkillRegistry.reset()

        os.environ["LOCAL_SKILLS_PATH"] = str(temp_skills_dir)
        os.environ["SKILLS_BASE_PATH"] = ""
        os.environ["ENABLE_BATCH_API"] = "true"

        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

        SkillRegistry.reset()
        get_settings.cache_clear()
        os.environ.pop("ENABLE_BATCH_API", None)

    def test_submit_batch_disabled(self, app_client: TestClient, test_api_key: str) -> None:
        """Test batch endpoint returns 501 when disabled."""
        response = app_client.post(
            "/api/v1/execute/batch",
            json={
                "documents": [{"id": "doc1", "content": "test"}],
                "skill_name": "test_schema",
            },
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 501

    def test_submit_batch_skill_not_found(
        self, batch_app_client: TestClient, test_api_key: str
    ) -> None:
        """Test batch endpoint returns 404 for unknown skill."""
        response = batch_app_client.post(
            "/api/v1/execute/batch",
            json={
                "documents": [{"id": "doc1", "content": "test"}],
                "skill_name": "nonexistent_schema",
            },
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 404

    def test_submit_batch_empty_documents(
        self, batch_app_client: TestClient, test_api_key: str
    ) -> None:
        """Test batch endpoint returns 400 for empty documents."""
        response = batch_app_client.post(
            "/api/v1/execute/batch",
            json={
                "documents": [],
                "skill_name": "test_schema",
            },
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 400

    def test_get_batch_status_disabled(self, app_client: TestClient, test_api_key: str) -> None:
        """Test batch status endpoint returns 501 when disabled."""
        response = app_client.get(
            "/api/v1/execute/batch/batch_123",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 501

    def test_get_batch_status_not_found(
        self, batch_app_client: TestClient, test_api_key: str
    ) -> None:
        """Test batch status endpoint returns 404 for unknown batch."""
        response = batch_app_client.get(
            "/api/v1/execute/batch/nonexistent_batch",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------
class TestBatchModels:
    """Tests for batch-related Pydantic models."""

    def test_document_item(self) -> None:
        """Test DocumentItem model."""
        doc = DocumentItem(id="doc1", content="Hello world")
        assert doc.id == "doc1"
        assert doc.content == "Hello world"

    def test_batch_execution_request(self) -> None:
        """Test BatchExecutionRequest model."""
        request = BatchExecutionRequest(
            documents=[
                DocumentItem(id="doc1", content="Content 1"),
                DocumentItem(id="doc2", content="Content 2"),
            ],
            skill_name="test_schema",
        )
        assert len(request.documents) == 2
        assert request.skill_name == "test_schema"
        assert request.vendor is None
        assert request.model is None

    def test_batch_execution_request_with_overrides(self) -> None:
        """Test BatchExecutionRequest with vendor/model overrides."""
        request = BatchExecutionRequest(
            documents=[DocumentItem(id="doc1", content="Content")],
            skill_name="test_schema",
            vendor="anthropic",
            model="claude-sonnet-4-20250514",
        )
        assert request.vendor == "anthropic"
        assert request.model == "claude-sonnet-4-20250514"

    def test_batch_execution_response(self) -> None:
        """Test BatchExecutionResponse model."""
        response = BatchExecutionResponse(
            batch_id="batch_abc123",
            status=BatchStatus.SUBMITTED,
            total_documents=5,
        )
        assert response.batch_id == "batch_abc123"
        assert response.status == BatchStatus.SUBMITTED
        assert response.total_documents == 5
        assert response.results is None
        assert response.completed_at is None
        assert response.created_at is not None

    def test_batch_status_values(self) -> None:
        """Test BatchStatus enum values."""
        assert BatchStatus.SUBMITTED == "submitted"
        assert BatchStatus.PROCESSING == "processing"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.FAILED == "failed"
        assert BatchStatus.CANCELING == "canceling"
        assert BatchStatus.EXPIRED == "expired"
