"""Tests for CosmosDB execution result storage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.execution import (
    ExecutionMetadata,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
    ValidationResult,
)
from app.services.cosmosdb import CosmosDBService


@pytest.fixture
def mock_response() -> ExecutionResponse:
    """Create a sample ExecutionResponse for testing."""
    return ExecutionResponse(
        status=ExecutionStatus.COMPLETED,
        skill_name="test_schema",
        data={"field1": "value1", "field2": 42},
        validation=ValidationResult(status="PASS", quality_score=95),
        metadata=ExecutionMetadata(
            execution_id="exec-123",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            models_used=["gemini-3-flash-preview"],
            vendors_used=["gemini"],
        ),
        error=None,
    )


class TestCosmosDBService:
    """Tests for CosmosDBService."""

    @pytest.mark.asyncio
    async def test_store_execution_result_upserts_correct_document(
        self, mock_response: ExecutionResponse
    ) -> None:
        """store_execution_result() should upsert a document with the right shape."""
        service = CosmosDBService()
        service._initialized = True
        service._container = AsyncMock()

        await service.store_execution_result(mock_response, source="realtime")

        service._container.upsert_item.assert_called_once()
        doc = service._container.upsert_item.call_args[0][0]

        assert doc["id"] == "exec-123"
        assert doc["skill_name"] == "test_schema"
        assert doc["status"] == "completed"
        assert doc["data"] == {"field1": "value1", "field2": 42}
        assert doc["validation"]["status"] == "PASS"
        assert doc["validation"]["quality_score"] == 95
        assert doc["source"] == "realtime"
        assert doc["document_id"] is None
        assert doc["batch_id"] is None
        assert "stored_at" in doc
        assert doc["error"] is None

    @pytest.mark.asyncio
    async def test_store_batch_result_includes_document_and_batch_ids(
        self, mock_response: ExecutionResponse
    ) -> None:
        """Batch results should include document_id and batch_id."""
        service = CosmosDBService()
        service._initialized = True
        service._container = AsyncMock()

        await service.store_execution_result(
            mock_response,
            source="batch",
            document_id="doc-456",
            batch_id="batch-789",
        )

        doc = service._container.upsert_item.call_args[0][0]
        assert doc["source"] == "batch"
        assert doc["document_id"] == "doc-456"
        assert doc["batch_id"] == "batch-789"

    @pytest.mark.asyncio
    async def test_store_skipped_when_not_initialized(
        self, mock_response: ExecutionResponse
    ) -> None:
        """Storage should be silently skipped when service is not initialized."""
        service = CosmosDBService()
        # _initialized defaults to False
        service._container = AsyncMock()

        await service.store_execution_result(mock_response)

        service._container.upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_skipped_when_container_is_none(
        self, mock_response: ExecutionResponse
    ) -> None:
        """Storage should be silently skipped when container is None."""
        service = CosmosDBService()
        service._initialized = True
        service._container = None

        # Should not raise
        await service.store_execution_result(mock_response)

    @pytest.mark.asyncio
    async def test_store_failure_is_logged_not_raised(
        self, mock_response: ExecutionResponse
    ) -> None:
        """A CosmosDB upsert failure should be caught and logged, not raised."""
        service = CosmosDBService()
        service._initialized = True
        service._container = AsyncMock()
        service._container.upsert_item.side_effect = Exception("CosmosDB unavailable")

        # Should not raise
        await service.store_execution_result(mock_response)

    @pytest.mark.asyncio
    async def test_initialize_without_credentials_logs_warning(self) -> None:
        """Initialization without credentials should log a warning and not set _initialized."""
        with patch("app.services.cosmosdb.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                cosmosdb_endpoint=None,
                cosmosdb_key=None,
            )
            service = CosmosDBService()
            await service.initialize()

        assert service._initialized is False
        assert service._container is None

    @pytest.mark.asyncio
    async def test_initialize_with_connection_error_logs_exception(self) -> None:
        """A connection error during initialization should be logged gracefully."""
        mock_cosmos_client = MagicMock(side_effect=Exception("Connection refused"))
        mock_aio = MagicMock()
        mock_aio.CosmosClient = mock_cosmos_client

        with (
            patch("app.services.cosmosdb.get_settings") as mock_settings,
            patch.dict(
                "sys.modules",
                {"azure": MagicMock(), "azure.cosmos": MagicMock(), "azure.cosmos.aio": mock_aio},
            ),
        ):
            mock_settings.return_value = MagicMock(
                cosmosdb_endpoint="https://test.documents.azure.com:443/",
                cosmosdb_key="test-key",
                cosmosdb_database="test-db",
                cosmosdb_container="test-container",
            )
            service = CosmosDBService()
            await service.initialize()

        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_close_resets_state(self) -> None:
        """close() should reset the client, container, and initialized flag."""
        service = CosmosDBService()
        service._client = AsyncMock()
        service._container = AsyncMock()
        service._initialized = True

        await service.close()

        assert service._client is None
        assert service._container is None
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_close_handles_error_gracefully(self) -> None:
        """close() should handle errors from the client without raising."""
        service = CosmosDBService()
        service._client = AsyncMock()
        service._client.close.side_effect = Exception("Close failed")
        service._container = AsyncMock()
        service._initialized = True

        # Should not raise
        await service.close()

        assert service._client is None
        assert service._initialized is False

    def test_build_document_shape(self, mock_response: ExecutionResponse) -> None:
        """_build_document should produce a well-formed CosmosDB document."""
        doc = CosmosDBService._build_document(
            mock_response,
            source="realtime",
            document_id=None,
            batch_id=None,
        )

        assert isinstance(doc, dict)
        assert doc["id"] == "exec-123"
        assert doc["skill_name"] == "test_schema"
        assert doc["status"] == "completed"
        assert doc["metadata"]["execution_id"] == "exec-123"
        assert doc["metadata"]["token_usage"]["total_tokens"] == 150
        assert isinstance(doc["skill_results"], list)
        assert isinstance(doc["stored_at"], str)

    def test_build_document_without_validation(self) -> None:
        """_build_document should handle None validation gracefully."""
        response = ExecutionResponse(
            status=ExecutionStatus.FAILED,
            skill_name="test_schema",
            data=None,
            validation=None,
            error="Something went wrong",
        )

        doc = CosmosDBService._build_document(response, "realtime", None, None)

        assert doc["validation"] is None
        assert doc["data"] is None
        assert doc["error"] == "Something went wrong"
        assert doc["status"] == "failed"
