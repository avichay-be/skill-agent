"""Execution API routes."""

import json
import logging
import os
from typing import Annotated, Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

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
from app.services.cosmosdb import get_cosmosdb_service
from app.services.executor import SkillExecutor, get_executor
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

    This endpoint uses LangGraph by default if use_langgraph is enabled,
    otherwise falls back to the legacy SkillExecutor.

    Args:
        exec_request: Execution request with document and skill_name.

    Returns:
        Extraction results with metadata.
    """
    settings = get_settings()

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
        f"document length: {len(exec_request.document)} chars, "
        f"using {'LangGraph' if settings.use_langgraph else 'Legacy Executor'}"
    )

    # Choose executor based on configuration
    if settings.use_langgraph:
        graph_executor = get_graph_executor()
        response = await graph_executor.execute(exec_request)
    else:
        legacy_executor = get_executor()
        response = await legacy_executor.execute(exec_request)

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

    # Store result in CosmosDB (fire-and-forget)
    cosmosdb = get_cosmosdb_service()
    if cosmosdb:
        await cosmosdb.store_execution_result(response, source="realtime")

    return response


@router.post("/file", response_model=ExecutionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def execute_extraction_from_file(
    request: Request,
    file: Annotated[UploadFile, File(description="Document file to process")],
    skill_name: Annotated[str, Form(description="Skill name to execute")],
    vendor: Annotated[Optional[str], Form(description="Override default LLM vendor")] = None,
    model: Annotated[Optional[str], Form(description="Override default model")] = None,
    _api_key: ApiKeyDep = None,  # type: ignore[assignment]
    registry: Annotated[Optional[SkillRegistry], Depends(get_registry)] = None,
    executor: Annotated[Optional[SkillExecutor], Depends(get_executor)] = None,
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

    # Validate file type/extension BEFORE reading content
    filename = file.filename or ""
    _, file_ext = os.path.splitext(filename)
    file_ext_lower = file_ext.lower()

    if not file_ext_lower or file_ext_lower not in settings.allowed_file_extensions:
        allowed = ", ".join(settings.allowed_file_extensions)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{file_ext_lower or '(none)'}' is not supported. "
                f"Allowed file extensions: {allowed}"
            ),
        )

    # Validate file size BEFORE reading full content
    # Read content to check size (FastAPI UploadFile requires reading to get size)
    content_bytes = await file.read()
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File size exceeds the maximum allowed size of {settings.max_upload_size_mb} MB."
            ),
        )

    # Decode file content
    try:
        document_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Try common encodings
        for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
            try:
                document_text = content_bytes.decode(encoding)
                logger.info(f"Successfully decoded file using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode file. Unsupported encoding. Please upload a text file or convert to UTF-8.",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading file: {str(e)}",
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
    )

    # Ensure executor is not None
    if executor is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Executor not available",
        )

    # Execute
    logger.info(
        f"Starting extraction from file '{file.filename}' ({file.content_type}), "
        f"skill '{skill_name}', document length: {len(document_text)} chars"
    )

    response = await executor.execute(exec_request)

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

    # Store result in CosmosDB (fire-and-forget)
    cosmosdb = get_cosmosdb_service()
    if cosmosdb:
        await cosmosdb.store_execution_result(response, source="realtime")

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

    Note: Only available when use_langgraph is enabled.

    Args:
        exec_request: Execution request with document and skill_name.

    Returns:
        StreamingResponse with Server-Sent Events
    """
    settings = get_settings()

    if not settings.use_langgraph or not settings.enable_streaming:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Streaming is only available with LangGraph enabled",
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
    feedback: Optional[Dict[str, Any]] = None,
    _api_key: ApiKeyDep = None,  # type: ignore[assignment]
) -> ExecutionResponse:
    """Resume a paused execution with optional human feedback.

    This endpoint is used to resume executions that were paused for
    human review. The human can provide corrections or approve the results.

    Note: Only available when use_langgraph is enabled.

    Args:
        execution_id: ID of the execution to resume
        feedback: Optional human feedback/corrections

    Returns:
        Execution results after resumption
    """
    settings = get_settings()

    if not settings.use_langgraph or not settings.enable_human_review:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Human review is only available with LangGraph enabled",
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


@router.post("/legacy", response_model=ExecutionResponse)
@limiter.limit("10/minute")  # type: ignore[misc]
async def execute_extraction_legacy(
    request: Request,
    exec_request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    executor: Annotated[SkillExecutor, Depends(get_executor)],
) -> ExecutionResponse:
    """Execute extraction using the legacy SkillExecutor.

    This endpoint always uses the original executor implementation,
    regardless of the use_langgraph setting. Useful for comparison
    or rollback scenarios.

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

    logger.info(
        f"Starting LEGACY extraction with skill '{exec_request.skill_name}', "
        f"document length: {len(exec_request.document)} chars"
    )

    response = await executor.execute(exec_request)

    # Log result
    if response.status == ExecutionStatus.COMPLETED:
        logger.info(f"Legacy extraction completed in {response.metadata.processing_time_ms}ms")
    elif response.status == ExecutionStatus.PARTIAL:
        logger.warning(f"Legacy extraction partially completed: {response.error}")
    else:
        logger.error(f"Legacy extraction failed: {response.error}")

    # Store result in CosmosDB (fire-and-forget)
    cosmosdb = get_cosmosdb_service()
    if cosmosdb:
        await cosmosdb.store_execution_result(response, source="realtime")

    return response


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
