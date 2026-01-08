"""Execution API routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

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
    """Execute document extraction using specified schema.

    Args:
        request: Execution request with document and schema.

    Returns:
        Extraction results with metadata.
    """
    # Validate schema exists
    schema = registry.get_schema(request.schema_id)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema '{request.schema_id}' not found",
        )

    # Validate skill_ids if provided
    if request.skill_ids:
        invalid_skills = [
            sid for sid in request.skill_ids if sid not in schema.skills
        ]
        if invalid_skills:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid skill IDs: {invalid_skills}",
            )

    # Execute
    logger.info(
        f"Starting extraction with schema '{request.schema_id}', "
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


@router.post("/single/{schema_id}/{skill_id}", response_model=ExecutionResponse)
async def execute_single_skill(
    schema_id: str,
    skill_id: str,
    document: str,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    executor: Annotated[SkillExecutor, Depends(get_executor)],
) -> ExecutionResponse:
    """Execute a single skill for testing/debugging.

    Args:
        schema_id: Schema containing the skill.
        skill_id: Skill to execute.
        document: Document content (in request body).

    Returns:
        Extraction results.
    """
    # Validate
    schema = registry.get_schema(schema_id)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema '{schema_id}' not found",
        )

    if skill_id not in schema.skills:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_id}' not found in schema '{schema_id}'",
        )

    # Execute single skill
    request = ExecutionRequest(
        document=document,
        schema_id=schema_id,
        skill_ids=[skill_id],
    )

    return await executor.execute(request)
