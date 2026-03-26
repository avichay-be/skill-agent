"""Workflow API routes."""

import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.file_uploads import read_uploaded_text_file
from app.core.config import get_settings
from app.core.rate_limiter import limiter
from app.core.security import ApiKeyDep
from app.models.workflow import (
    WorkflowDetailResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowListResponse,
)
from app.services.skill_registry import SkillRegistry, get_registry
from app.services.workflow_executor import WorkflowExecutor, get_workflow_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _normalize_schema_ids(schema_ids: list[str] | None) -> list[str] | None:
    """Normalize schema IDs from JSON or multipart form input."""
    if schema_ids is None:
        return None

    normalized = [schema_id.strip() for schema_id in schema_ids if schema_id.strip()]
    return normalized or None


def _validate_workflow_request(
    workflow_request: WorkflowExecutionRequest,
    registry: SkillRegistry,
) -> None:
    """Validate whether the request targets a saved or ephemeral workflow."""
    schema_ids = _normalize_schema_ids(workflow_request.schema_ids)
    workflow_request.schema_ids = schema_ids

    if workflow_request.workflow_id and schema_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either workflow_id or schema_ids, not both",
        )

    if schema_ids:
        if len(schema_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dynamic workflows require at least 2 schema_ids",
            )

        missing_schema_ids = [
            schema_id for schema_id in schema_ids if not registry.get_schema(schema_id)
        ]
        if missing_schema_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow references missing schemas: {missing_schema_ids}",
            )
        return

    if not workflow_request.workflow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either workflow_id or schema_ids must be provided",
        )

    loaded = registry.get_workflow(workflow_request.workflow_id)
    if not loaded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_request.workflow_id}' not found",
        )

    missing: list[str] = []
    for step in loaded.config.steps:
        if not registry.get_schema(step.schema_id):
            missing.append(step.schema_id)

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow references missing schemas: {missing}",
        )


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
    _validate_workflow_request(workflow_request, registry)

    logger.info(
        f"Executing workflow target '{workflow_request.workflow_id or workflow_request.schema_ids}', "
        f"document length: {len(workflow_request.document)} chars"
    )

    response = await executor.execute(workflow_request)

    return response


@router.post("/execute/file", response_model=WorkflowExecutionResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def execute_workflow_from_file(
    request: Request,
    file: Annotated[UploadFile, File(description="Document file to process")],
    workflow_id: Annotated[str | None, Form(description="Workflow ID to execute")] = None,
    schema_ids: Annotated[
        list[str] | None,
        Form(description="Ordered schema IDs for an ephemeral composed workflow"),
    ] = None,
    workflow_name: Annotated[
        str | None,
        Form(description="Optional display name for an ephemeral composed workflow"),
    ] = None,
    workflow_description: Annotated[
        str | None,
        Form(description="Optional description for an ephemeral composed workflow"),
    ] = None,
    vendor: Annotated[str | None, Form(description="Override default LLM vendor")] = None,
    model: Annotated[str | None, Form(description="Override default model")] = None,
    save_to_cosmos: Annotated[
        bool, Form(description="Whether to persist result to CosmosDB")
    ] = False,
    _api_key: ApiKeyDep = None,  # type: ignore[assignment]
    registry: Annotated[SkillRegistry, Depends(get_registry)] = None,  # type: ignore[assignment]
    executor: Annotated[WorkflowExecutor, Depends(get_workflow_executor)] = None,  # type: ignore[assignment]
) -> WorkflowExecutionResponse:
    """Execute a workflow using uploaded file content as the initial document."""
    settings = get_settings()
    document_text = await read_uploaded_text_file(
        file,
        allowed_file_extensions=settings.allowed_file_extensions,
        max_upload_size_mb=settings.max_upload_size_mb,
    )

    workflow_request = WorkflowExecutionRequest(
        document=document_text,
        workflow_id=workflow_id,
        schema_ids=_normalize_schema_ids(schema_ids),
        workflow_name=workflow_name,
        workflow_description=workflow_description,
        vendor=vendor,
        model=model,
        save_to_cosmos=save_to_cosmos,
    )

    return cast(
        WorkflowExecutionResponse,
        await execute_workflow(
            request=request,
            workflow_request=workflow_request,
            _api_key=_api_key,
            registry=registry,
            executor=executor,
        ),
    )
