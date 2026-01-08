"""Execution API routes."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.security import ApiKeyDep
from app.models.execution import ExecutionRequest, ExecutionResponse, ExecutionStatus
from app.services.executor import SkillExecutor, get_executor
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execute", tags=["execution"])


@router.post("", response_model=ExecutionResponse)
async def execute_extraction(
    request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    executor: Annotated[SkillExecutor, Depends(get_executor)],
) -> ExecutionResponse:
    """Execute document extraction using specified skill.

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

    # Execute
    logger.info(
        f"Starting extraction with skill '{request.skill_name}', "
        f"document length: {len(request.document)} chars"
    )

    response = await executor.execute(request)

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
