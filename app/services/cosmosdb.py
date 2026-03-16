"""CosmosDB service for persisting execution results."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.models.execution import ExecutionResponse
from app.models.workflow import WorkflowExecutionResponse

logger = logging.getLogger(__name__)


class CosmosDBService:
    """Async service for storing execution results in Azure CosmosDB."""

    def __init__(self) -> None:
        self._client: Any = None
        self._container: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize CosmosDB client, database, and container references.

        Logs a warning and returns gracefully if credentials are missing
        or connection fails.
        """
        settings = get_settings()

        if not settings.cosmosdb_endpoint or not settings.cosmosdb_key:
            logger.warning(
                "CosmosDB credentials not configured "
                "(COSMOSDB_ENDPOINT / COSMOSDB_KEY). Storage disabled."
            )
            return

        try:
            from azure.cosmos.aio import (  # type: ignore[import-untyped,import-not-found]
                CosmosClient,
            )

            self._client = CosmosClient(
                settings.cosmosdb_endpoint, credential=settings.cosmosdb_key
            )
            # Cache account info
            await self._client.__aenter__()

            database = self._client.get_database_client(settings.cosmosdb_database)
            self._container = database.get_container_client(settings.cosmosdb_container)
            self._initialized = True
            logger.info(
                "CosmosDB initialized: database=%s, container=%s",
                settings.cosmosdb_database,
                settings.cosmosdb_container,
            )
        except Exception:
            logger.exception("Failed to initialize CosmosDB client")
            self._client = None
            self._container = None

    async def store_execution_result(
        self,
        response: ExecutionResponse,
        source: str = "realtime",
        document_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> None:
        """Persist an ExecutionResponse to CosmosDB.

        This is fire-and-forget: errors are logged, never raised.

        Args:
            response: The execution response to store.
            source: Origin of the result — "realtime" or "batch".
            document_id: Caller's document ID (batch results).
            batch_id: Batch ID (batch results).
        """
        if not self._initialized or self._container is None:
            return

        try:
            doc = self._build_document(response, source, document_id, batch_id)
            await self._container.upsert_item(doc)
            logger.debug("Stored execution result %s in CosmosDB", doc["id"])
        except Exception:
            logger.exception(
                "Failed to store execution result %s in CosmosDB",
                response.metadata.execution_id,
            )

    @staticmethod
    def _build_document(
        response: ExecutionResponse,
        source: str,
        document_id: Optional[str],
        batch_id: Optional[str],
    ) -> Dict[str, Any]:
        """Build a CosmosDB document from an ExecutionResponse."""
        return {
            "id": response.metadata.execution_id,
            "skill_name": response.skill_name,
            "status": response.status.value,
            "data": response.data,
            "validation": response.validation.model_dump() if response.validation else None,
            "metadata": response.metadata.model_dump(mode="json"),
            "skill_results": [r.model_dump(mode="json") for r in response.skill_results],
            "error": response.error,
            "source": source,
            "document_id": document_id,
            "batch_id": batch_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

    async def store_workflow_result(
        self,
        response: WorkflowExecutionResponse,
    ) -> None:
        """Persist a WorkflowExecutionResponse to CosmosDB.

        Fire-and-forget: errors are logged, never raised.

        Args:
            response: The workflow execution response to store.
        """
        if not self._initialized or self._container is None:
            return

        try:
            doc: Dict[str, Any] = {
                "id": response.metadata.execution_id,
                "type": "workflow_execution",
                "workflow_id": response.workflow_id,
                "workflow_name": response.workflow_name,
                "status": response.status.value,
                "data": response.data,
                "metadata": response.metadata.model_dump(mode="json"),
                "step_results": [r.model_dump(mode="json") for r in response.step_results],
                "error": response.error,
                "stored_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._container.upsert_item(doc)
            logger.debug("Stored workflow result %s in CosmosDB", response.metadata.execution_id)
        except Exception:
            logger.exception(
                "Failed to store workflow result %s in CosmosDB",
                response.metadata.execution_id,
            )

    async def close(self) -> None:
        """Close the CosmosDB client connection."""
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("CosmosDB client closed")
            except Exception:
                logger.exception("Error closing CosmosDB client")
            finally:
                self._client = None
                self._container = None
                self._initialized = False


_cosmosdb_service: Optional[CosmosDBService] = None


def get_cosmosdb_service() -> Optional[CosmosDBService]:
    """Get the CosmosDB service singleton (None if not enabled)."""
    return _cosmosdb_service


async def initialize_cosmosdb_service() -> None:
    """Create and initialize the global CosmosDB service."""
    global _cosmosdb_service
    _cosmosdb_service = CosmosDBService()
    await _cosmosdb_service.initialize()


async def close_cosmosdb_service() -> None:
    """Close and clear the global CosmosDB service."""
    global _cosmosdb_service
    if _cosmosdb_service is not None:
        await _cosmosdb_service.close()
        _cosmosdb_service = None
