"""Schemas API routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import ApiKeyDep
from app.models.schema import SchemaDetailResponse, SchemaListResponse
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("", response_model=SchemaListResponse)
async def list_schemas(
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> SchemaListResponse:
    """List all available schemas."""
    schemas = registry.list_schemas()

    return SchemaListResponse(
        schemas=schemas,
        total=len(schemas),
    )


@router.get("/{schema_id}", response_model=SchemaDetailResponse)
async def get_schema(
    schema_id: str,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> SchemaDetailResponse:
    """Get schema details with all skills."""
    loaded = registry.get_schema(schema_id)

    if not loaded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema '{schema_id}' not found",
        )

    return SchemaDetailResponse(
        schema=loaded.config,
        skills=list(loaded.skills.values()),
        git_commit=loaded.git_commit,
        loaded_at=loaded.loaded_at,
    )


@router.post("/{schema_id}/reload")
async def reload_schema(
    schema_id: str,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> Dict[str, Any]:
    """Force reload a specific schema from Git."""
    try:
        loaded = registry.reload_schema(schema_id)
        return {
            "status": "success",
            "schema_id": schema_id,
            "version": loaded.config.version,
            "git_commit": loaded.git_commit,
            "skills_count": len(loaded.skills),
        }
    except Exception as e:
        logger.exception(f"Failed to reload schema '{schema_id}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload schema: {e}",
        )
