"""Execution API routes."""

import json
import logging
from typing import Annotated, Optional, Dict, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.security import ApiKeyDep
from app.core.config import get_settings
from app.models.execution import ExecutionRequest, ExecutionResponse, ExecutionStatus
from app.services.executor import SkillExecutor, get_executor
from app.services.graph_executor import GraphExecutor, get_graph_executor
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execute", tags=["execution"])


@router.post("", response_model=ExecutionResponse)
async def execute_extraction(
    request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> ExecutionResponse:
    """Execute document extraction using specified skill.

    This endpoint uses LangGraph by default if use_langgraph is enabled,
    otherwise falls back to the legacy SkillExecutor.

    Args:
        request: Execution request with document and skill_name.

    Returns:
        Extraction results with metadata.
    """
    settings = get_settings()

    # Validate skill exists
    schema = registry.get_schema(request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{request.skill_name}' not found",
        )

    # Execute
    logger.info(
        f"Starting extraction with skill '{request.skill_name}', "
        f"document length: {len(request.document)} chars, "
        f"using {'LangGraph' if settings.use_langgraph else 'Legacy Executor'}"
    )

    # Choose executor based on configuration
    if settings.use_langgraph:
        graph_executor = get_graph_executor()
        response = await graph_executor.execute(request)
    else:
        legacy_executor = get_executor()
        response = await legacy_executor.execute(request)

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
async def execute_extraction_from_file(
    file: Annotated[UploadFile, File(description="Document file to process")],
    skill_name: Annotated[str, Form(description="Skill name to execute")],
    vendor: Annotated[Optional[str], Form(description="Override default LLM vendor")] = None,
    model: Annotated[Optional[str], Form(description="Override default model")] = None,
    _api_key: ApiKeyDep = None,
    registry: Annotated[SkillRegistry, Depends(get_registry)] = None,
    executor: Annotated[SkillExecutor, Depends(get_executor)] = None,
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
    # Read file content
    try:
        content_bytes = await file.read()
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
                detail=f"Unable to decode file. Unsupported encoding. Please upload a text file or convert to UTF-8.",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading file: {str(e)}",
        )

    # Validate skill exists
    schema = registry.get_schema(skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found",
        )

    # Create execution request
    request = ExecutionRequest(
        document=document_text,
        skill_name=skill_name,
        vendor=vendor,
        model=model,
    )

    # Execute
    logger.info(
        f"Starting extraction from file '{file.filename}' ({file.content_type}), "
        f"skill '{skill_name}', document length: {len(document_text)} chars"
    )

    response = await executor.execute(request)

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
async def execute_extraction_streaming(
    request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
):
    """Execute extraction with real-time streaming updates (Server-Sent Events).

    This endpoint streams progress events as the LangGraph executes,
    enabling real-time UI updates.

    Note: Only available when use_langgraph is enabled.

    Args:
        request: Execution request with document and skill_name.

    Returns:
        StreamingResponse with Server-Sent Events
    """
    settings = get_settings()

    if not settings.use_langgraph or not settings.enable_streaming:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Streaming is only available with LangGraph enabled"
        )

    # Validate skill exists
    schema = registry.get_schema(request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{request.skill_name}' not found",
        )

    logger.info(
        f"Starting streaming extraction with skill '{request.skill_name}'"
    )

    async def event_generator():
        """Generate Server-Sent Events from graph execution."""
        try:
            graph_executor = get_graph_executor()
            async for event in graph_executor.execute_streaming(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception(f"Streaming failed: {e}")
            error_event = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.post("/resume/{execution_id}", response_model=ExecutionResponse)
async def resume_execution(
    execution_id: str,
    feedback: Optional[Dict[str, Any]] = None,
    _api_key: ApiKeyDep = None,
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
            detail="Human review is only available with LangGraph enabled"
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
            detail=f"Failed to resume execution: {str(e)}"
        )


@router.post("/legacy", response_model=ExecutionResponse)
async def execute_extraction_legacy(
    request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    executor: Annotated[SkillExecutor, Depends(get_executor)],
) -> ExecutionResponse:
    """Execute extraction using the legacy SkillExecutor.

    This endpoint always uses the original executor implementation,
    regardless of the use_langgraph setting. Useful for comparison
    or rollback scenarios.

    Args:
        request: Execution request with document and skill_name.

    Returns:
        Extraction results with metadata.
    """
    # Validate skill exists
    schema = registry.get_schema(request.skill_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{request.skill_name}' not found",
        )

    logger.info(
        f"Starting LEGACY extraction with skill '{request.skill_name}', "
        f"document length: {len(request.document)} chars"
    )

    response = await executor.execute(request)

    # Log result
    if response.status == ExecutionStatus.COMPLETED:
        logger.info(
            f"Legacy extraction completed in {response.metadata.processing_time_ms}ms"
        )
    elif response.status == ExecutionStatus.PARTIAL:
        logger.warning(f"Legacy extraction partially completed: {response.error}")
    else:
        logger.error(f"Legacy extraction failed: {response.error}")

    return response
