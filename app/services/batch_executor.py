"""Batch Executor - Orchestrates Anthropic Batch API submissions and results."""

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional

from app.core.config import Settings, get_settings
from app.models.execution import (
    BatchExecutionRequest,
    BatchExecutionResponse,
    BatchStatus,
    ExecutionMetadata,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
)
from app.services.cosmosdb import get_cosmosdb_service
from app.services.llm_client import AnthropicClient, LLMClientError, LLMClientFactory
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)


class BatchExecutorError(Exception):
    """Error during batch execution."""

    pass


class BatchMetadata:
    """In-memory metadata for a submitted batch."""

    def __init__(
        self,
        batch_id: str,
        skill_name: str,
        document_ids: list[str],
        model: str,
        vendor: str,
        created_at: datetime,
        custom_id_to_doc_skill: Dict[str, Dict[str, str]],
    ):
        self.batch_id = batch_id
        self.skill_name = skill_name
        self.document_ids = document_ids
        self.model = model
        self.vendor = vendor
        self.created_at = created_at
        self.custom_id_to_doc_skill = custom_id_to_doc_skill


class BatchExecutor:
    """Executes document batches via Anthropic Batch API."""

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        settings: Optional[Settings] = None,
    ):
        self.registry = registry or get_registry()
        self.settings = settings or get_settings()
        self._batches: Dict[str, BatchMetadata] = {}
        self._lock = Lock()

    def _get_anthropic_client(self, model: Optional[str] = None) -> AnthropicClient:
        """Get an AnthropicClient instance.

        Args:
            model: Optional model override.

        Returns:
            AnthropicClient instance.

        Raises:
            BatchExecutorError: If client is not an AnthropicClient.
        """
        client = LLMClientFactory.get_client("anthropic", model, self.settings)
        if not isinstance(client, AnthropicClient):
            raise BatchExecutorError("Batch API requires an AnthropicClient")
        return client

    async def submit_batch(
        self,
        request: BatchExecutionRequest,
    ) -> BatchExecutionResponse:
        """Submit a batch of documents for processing.

        For each document, builds batch request params for every skill in the schema,
        then submits a single batch to the Anthropic API.

        Args:
            request: Batch execution request with documents and skill_name.

        Returns:
            BatchExecutionResponse with batch_id and submitted status.
        """
        schema = self.registry.get_schema_or_raise(request.skill_name)

        skills = schema.get_active_skills()
        if not skills:
            raise BatchExecutorError(f"No active skills in schema '{request.skill_name}'")

        vendor = request.vendor or "anthropic"
        if vendor != "anthropic":
            raise BatchExecutorError(
                f"Batch API is only supported with Anthropic. Got vendor='{vendor}'"
            )

        model = request.model or self.settings.anthropic_model
        client = self._get_anthropic_client(model)

        # Build batch requests: one per (document, skill) pair
        batch_requests: list[tuple[str, str, str, float, int]] = []
        custom_id_to_doc_skill: Dict[str, Dict[str, str]] = {}

        for doc in request.documents:
            for skill in skills:
                custom_id = f"{doc.id}|{skill.id}"
                batch_requests.append(
                    (
                        custom_id,
                        skill.prompt,
                        doc.content,
                        skill.config.temperature,
                        4096,
                    )
                )
                custom_id_to_doc_skill[custom_id] = {
                    "document_id": doc.id,
                    "skill_id": skill.id,
                }

        # Submit to Anthropic
        batch_id = await client.create_batch(batch_requests)

        now = datetime.now(timezone.utc)
        metadata = BatchMetadata(
            batch_id=batch_id,
            skill_name=request.skill_name,
            document_ids=[d.id for d in request.documents],
            model=model,
            vendor=vendor,
            created_at=now,
            custom_id_to_doc_skill=custom_id_to_doc_skill,
        )
        with self._lock:
            self._batches[batch_id] = metadata

        return BatchExecutionResponse(
            batch_id=batch_id,
            status=BatchStatus.SUBMITTED,
            total_documents=len(request.documents),
            created_at=now,
        )

    async def get_batch_status(
        self,
        batch_id: str,
    ) -> BatchExecutionResponse:
        """Get the status (and results if completed) for a batch.

        Args:
            batch_id: Anthropic batch ID.

        Returns:
            BatchExecutionResponse with current status and optional results.
        """
        with self._lock:
            metadata = self._batches.get(batch_id)

        if metadata is None:
            raise BatchExecutorError(f"Unknown batch ID: {batch_id}")

        client = self._get_anthropic_client(metadata.model)

        try:
            status_info = await client.get_batch_status(batch_id)
        except LLMClientError as e:
            raise BatchExecutorError(f"Failed to get batch status: {e}")

        processing_status = status_info["processing_status"]
        request_counts = status_info["request_counts"]

        # Map Anthropic status to our BatchStatus
        if processing_status == "in_progress":
            batch_status = BatchStatus.PROCESSING
        elif processing_status == "canceling":
            batch_status = BatchStatus.CANCELING
        elif processing_status == "ended":
            # Check if all succeeded
            if request_counts.get("errored", 0) > 0 or request_counts.get("expired", 0) > 0:
                if request_counts.get("succeeded", 0) > 0:
                    batch_status = BatchStatus.COMPLETED
                else:
                    batch_status = BatchStatus.FAILED
            else:
                batch_status = BatchStatus.COMPLETED
        else:
            batch_status = BatchStatus.PROCESSING

        response = BatchExecutionResponse(
            batch_id=batch_id,
            status=batch_status,
            total_documents=len(metadata.document_ids),
            created_at=metadata.created_at,
            request_counts=request_counts,
        )

        # If ended, fetch results
        if processing_status == "ended":
            response.completed_at = datetime.now(timezone.utc)
            try:
                results = await self._fetch_and_parse_results(client, batch_id, metadata)
                response.results = results
            except LLMClientError as e:
                logger.error(f"Failed to fetch batch results: {e}")
                response.status = BatchStatus.FAILED

        return response

    async def _fetch_and_parse_results(
        self,
        client: AnthropicClient,
        batch_id: str,
        metadata: BatchMetadata,
    ) -> Dict[str, ExecutionResponse]:
        """Fetch batch results and group by document ID.

        Args:
            client: Anthropic client.
            batch_id: Batch ID.
            metadata: Batch metadata with mapping info.

        Returns:
            Dict of document_id → ExecutionResponse.
        """
        raw_results = await client.get_batch_results(batch_id)

        # Group results by document_id
        doc_results: Dict[str, Dict[str, Any]] = {}
        doc_token_usage: Dict[str, Dict[str, TokenUsage]] = {}

        for custom_id, (text, usage) in raw_results.items():
            mapping = metadata.custom_id_to_doc_skill.get(custom_id)
            if not mapping:
                logger.warning(f"Unknown custom_id in batch results: {custom_id}")
                continue

            doc_id = mapping["document_id"]
            skill_id = mapping["skill_id"]

            if doc_id not in doc_results:
                doc_results[doc_id] = {}
                doc_token_usage[doc_id] = {}

            # Parse JSON from response text
            if text:
                try:
                    parsed = client._extract_json_from_text(text)
                    doc_results[doc_id][skill_id] = parsed
                except LLMClientError:
                    logger.warning(f"Failed to parse JSON for doc={doc_id}, skill={skill_id}")
                    doc_results[doc_id][skill_id] = {"_raw": text}

            doc_token_usage[doc_id][skill_id] = usage

        # Build ExecutionResponse per document
        responses: Dict[str, ExecutionResponse] = {}
        for doc_id in metadata.document_ids:
            skill_data = doc_results.get(doc_id, {})
            skill_usage = doc_token_usage.get(doc_id, {})

            # Merge all skill results into a single data dict
            merged_data: Dict[str, Any] = {}
            for skill_id, data in skill_data.items():
                if isinstance(data, dict):
                    merged_data.update(data)

            # Sum token usage
            total_usage = TokenUsage()
            for usage in skill_usage.values():
                total_usage.input_tokens += usage.input_tokens
                total_usage.output_tokens += usage.output_tokens
                total_usage.total_tokens += usage.total_tokens

            exec_metadata = ExecutionMetadata(
                token_usage=total_usage,
                token_usage_by_skill=skill_usage,
                models_used=[metadata.model],
                vendors_used=[metadata.vendor],
                completed_at=datetime.now(timezone.utc),
            )

            status = ExecutionStatus.COMPLETED if skill_data else ExecutionStatus.FAILED

            responses[doc_id] = ExecutionResponse(
                status=status,
                skill_name=metadata.skill_name,
                data=merged_data if merged_data else None,
                metadata=exec_metadata,
            )

        # Store each per-document result in CosmosDB (fire-and-forget)
        cosmosdb = get_cosmosdb_service()
        if cosmosdb:
            for doc_id, resp in responses.items():
                await cosmosdb.store_execution_result(
                    resp,
                    source="batch",
                    document_id=doc_id,
                    batch_id=batch_id,
                )

        return responses


_batch_executor: Optional[BatchExecutor] = None


def get_batch_executor() -> BatchExecutor:
    """Get or create the batch executor singleton."""
    global _batch_executor
    if _batch_executor is None:
        _batch_executor = BatchExecutor()
    return _batch_executor
