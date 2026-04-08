"""Execution API routes."""

import json
import logging
from typing import Annotated, Any, AsyncGenerator

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.file_uploads import read_uploaded_text_file
from app.core.config import get_settings
from app.core.rate_limiter import limiter
from app.core.security import ApiKeyDep
from app.models.execution import (
    BatchExecutionRequest,
    BatchExecutionResponse,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
)
from app.services.batch_executor import BatchExecutor, BatchExecutorError, get_batch_executor
from app.services.graph_executor import get_graph_executor
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execute", tags=["execution"])


@router.post("", response_model=ExecutionResponse)
@limiter.limit("10/minute")  # type: ignore[misc]
async def execute_extraction(
    request: Request,
    exec_request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> ExecutionResponse:
    """Execute document extraction using specified skill.

    Args:
        exec_request: Execution request with document and skill_name.

    Returns:
        Extraction results with metadata.
    """
    # Validate skill exists
    schema = registry.get_schema(exec_request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{exec_request.skill_name}' not found",
        )

    # Execute
    logger.info(
        f"Starting extraction with skill '{exec_request.skill_name}', "
        f"document length: {len(exec_request.document)} chars"
    )

    graph_executor = get_graph_executor()
    response = await graph_executor.execute(exec_request)

    # Log result
    if response.status == ExecutionStatus.COMPLETED:
        logger.info(
            f"Extraction completed in {response.metadata.processing_time_ms}ms, "
            f"tokens: {response.metadata.token_usage.total_tokens}"
        )
    elif response.status == ExecutionStatus.PARTIAL:
        logger.warning(f"Extraction partially completed: {response.error}")
    else:
        logger.error(f"Extraction failed: {response.error}")

    return response


@router.post("/file", response_model=ExecutionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def execute_extraction_from_file(
    request: Request,
    file: Annotated[UploadFile, File(description="Document file to process")],
    skill_name: Annotated[str, Form(description="Skill name to execute")],
    vendor: Annotated[str | None, Form(description="Override default LLM vendor")] = None,
    model: Annotated[str | None, Form(description="Override default model")] = None,
    save_to_cosmos: Annotated[
        bool, Form(description="Whether to persist result to CosmosDB")
    ] = False,
    _api_key: ApiKeyDep = None,  # type: ignore[assignment]
    registry: Annotated[SkillRegistry | None, Depends(get_registry)] = None,
) -> ExecutionResponse:
    """Execute document extraction from an uploaded file.

    Supports text files, PDFs, and other document formats.
    Use this endpoint for large documents instead of embedding content in JSON.

    Args:
        file: Document file to process (multipart/form-data)
        skill_name: Skill to execute
        vendor: Optional LLM vendor override
        model: Optional model override

    Returns:
        Extraction results with metadata.
    """
    settings = get_settings()

    document_text = await read_uploaded_text_file(
        file,
        allowed_file_extensions=settings.allowed_file_extensions,
        max_upload_size_mb=settings.max_upload_size_mb,
    )

    # Ensure registry is not None
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registry not available",
        )

    # Validate skill exists
    schema = registry.get_schema(skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    # Create execution request
    exec_request = ExecutionRequest(
        document=document_text,
        skill_name=skill_name,
        vendor=vendor,
        model=model,
        save_to_cosmos=save_to_cosmos,
    )

    # Execute
    logger.info(
        f"Starting extraction from file '{file.filename}' ({file.content_type}), "
        f"skill '{skill_name}', document length: {len(document_text)} chars"
    )

    graph_executor = get_graph_executor()
    response = await graph_executor.execute(exec_request)

    # Log result
    if response.status == ExecutionStatus.COMPLETED:
        logger.info(
            f"File extraction completed in {response.metadata.processing_time_ms}ms, "
            f"tokens: {response.metadata.token_usage.total_tokens}"
        )
    elif response.status == ExecutionStatus.PARTIAL:
        logger.warning(f"File extraction partially completed: {response.error}")
    else:
        logger.error(f"File extraction failed: {response.error}")

    return response


@router.post("/stream")
@limiter.limit("5/minute")  # type: ignore[misc]
async def execute_extraction_streaming(
    request: Request,
    exec_request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> StreamingResponse:
    """Execute extraction with real-time streaming updates (Server-Sent Events).

    This endpoint streams progress events as the LangGraph executes,
    enabling real-time UI updates.

    Note: Only available when streaming is enabled.

    Args:
        exec_request: Execution request with document and skill_name.

    Returns:
        StreamingResponse with Server-Sent Events
    """
    settings = get_settings()

    if not settings.enable_streaming:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Streaming is disabled",
        )

    # Validate skill exists
    schema = registry.get_schema(exec_request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{exec_request.skill_name}' not found",
        )

    logger.info(f"Starting streaming extraction with skill '{exec_request.skill_name}'")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events from graph execution."""
        try:
            graph_executor = get_graph_executor()
            async for event in graph_executor.execute_streaming(exec_request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception(f"Streaming failed: {e}")
            error_event = {"type": "error", "error": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/resume/{execution_id}", response_model=ExecutionResponse)
@limiter.limit("10/minute")  # type: ignore[misc]
async def resume_execution(
    request: Request,
    execution_id: str,
    feedback: dict[str, Any] | None = None,
    _api_key: ApiKeyDep = None,  # type: ignore[assignment]
) -> ExecutionResponse:
    """Resume a paused execution with optional human feedback.

    This endpoint is used to resume executions that were paused for
    human review. The human can provide corrections or approve the results.

    Note: Only available when human review is enabled.

    Args:
        execution_id: ID of the execution to resume
        feedback: Optional human feedback/corrections

    Returns:
        Execution results after resumption
    """
    settings = get_settings()

    if not settings.enable_human_review:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Human review is disabled",
        )

    logger.info(f"Resuming execution {execution_id} with feedback: {bool(feedback)}")

    try:
        graph_executor = get_graph_executor()
        response = await graph_executor.resume_execution(execution_id, feedback)
        return response
    except Exception as e:
        logger.exception(f"Failed to resume execution {execution_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume execution: {str(e)}",
        )


@router.post("/batch", response_model=BatchExecutionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def submit_batch_execution(
    request: Request,
    batch_request: BatchExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    batch_executor: Annotated[BatchExecutor, Depends(get_batch_executor)],
) -> BatchExecutionResponse:
    """Submit a batch of documents for async extraction via Anthropic Batch API.

    This endpoint submits documents for background processing at 50% cost reduction.
    Batch jobs typically complete within 1 hour (max 24 hours).
    Use GET /execute/batch/{batch_id} to poll for results.

    Note: Only available with Anthropic vendor and when enable_batch_api is True.

    Args:
        batch_request: Batch request with documents and skill_name.

    Returns:
        BatchExecutionResponse with batch_id for polling.
    """
    settings = get_settings()

    if not settings.enable_batch_api:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Batch API is not enabled. Set ENABLE_BATCH_API=true.",
        )

    # Validate skill exists
    schema = registry.get_schema(batch_request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{batch_request.skill_name}' not found",
        )

    if not batch_request.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents provided",
        )

    logger.info(
        f"Submitting batch: skill='{batch_request.skill_name}', "
        f"documents={len(batch_request.documents)}"
    )

    try:
        response = await batch_executor.submit_batch(batch_request)
        logger.info(f"Batch submitted: {response.batch_id}")
        return response
    except BatchExecutorError as e:
        logger.error(f"Batch submission failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/batch/{batch_id}", response_model=BatchExecutionResponse)
@limiter.limit("30/minute")  # type: ignore[misc]
async def get_batch_execution_status(
    request: Request,
    batch_id: str,
    _api_key: ApiKeyDep,
    batch_executor: Annotated[BatchExecutor, Depends(get_batch_executor)],
) -> BatchExecutionResponse:
    """Get the status and results of a batch execution.

    Poll this endpoint to check batch progress. When status is 'completed',
    the results field contains extraction results keyed by document ID.

    Args:
        batch_id: Batch ID returned from POST /execute/batch.

    Returns:
        BatchExecutionResponse with status and optional results.
    """
    settings = get_settings()

    if not settings.enable_batch_api:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Batch API is not enabled. Set ENABLE_BATCH_API=true.",
        )

    try:
        response = await batch_executor.get_batch_status(batch_id)
        return response
    except BatchExecutorError as e:
        logger.error(f"Batch status retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
