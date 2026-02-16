"""Workflow API routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limiter import limiter
from app.core.security import ApiKeyDep
from app.models.workflow import (
    WorkflowDetailResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowListResponse,
)
from app.services.cosmosdb import get_cosmosdb_service
from app.services.skill_registry import SkillRegistry, get_registry
from app.services.workflow_executor import WorkflowExecutor, get_workflow_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    _api_key: ApiKeyDep,
) -> WorkflowListResponse:
    """List all available workflows."""
    configs = registry.list_workflows()
    return WorkflowListResponse(workflows=configs, total=len(configs))


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: str,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    _api_key: ApiKeyDep,
) -> WorkflowDetailResponse:
    """Get workflow detail with schema validation status."""
    loaded = registry.get_workflow(workflow_id)
    if not loaded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )

    # Check which schemas are missing
    missing: list[str] = []
    for step in loaded.config.steps:
        if not registry.get_schema(step.schema_id):
            missing.append(step.schema_id)

    return WorkflowDetailResponse(
        workflow=loaded.config,
        git_commit=loaded.git_commit,
        loaded_at=loaded.loaded_at,
        schemas_valid=len(missing) == 0,
        missing_schemas=missing,
    )


@router.post("/execute", response_model=WorkflowExecutionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def execute_workflow(
    request: Request,
    workflow_request: WorkflowExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    executor: Annotated[WorkflowExecutor, Depends(get_workflow_executor)],
) -> WorkflowExecutionResponse:
    """Execute a multi-schema workflow.

    Runs each step sequentially, chaining the JSON output of one schema
    as the document input for the next.

    Args:
        workflow_request: Workflow execution request with document and workflow_id.

    Returns:
        WorkflowExecutionResponse with all step results.
    """
    # Validate workflow exists
    loaded = registry.get_workflow(workflow_request.workflow_id)
    if not loaded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_request.workflow_id}' not found",
        )

    # Validate all referenced schemas exist
    missing: list[str] = []
    for step in loaded.config.steps:
        if not registry.get_schema(step.schema_id):
            missing.append(step.schema_id)

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow references missing schemas: {missing}",
        )

    logger.info(
        f"Executing workflow '{workflow_request.workflow_id}', "
        f"document length: {len(workflow_request.document)} chars"
    )

    response = await executor.execute(workflow_request)

    # Store result in CosmosDB (fire-and-forget)
    if workflow_request.save_to_cosmos:
        cosmosdb = get_cosmosdb_service()
        if cosmosdb:
            await cosmosdb.store_workflow_result(response)

    return response
