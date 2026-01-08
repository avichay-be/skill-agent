"""Skills API routes."""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import ApiKeyDep
from app.models.skill import Skill, SkillListResponse
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillListResponse)
async def list_skills(
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    schema_id: Optional[str] = Query(None, description="Filter by schema ID"),
) -> SkillListResponse:
    """List all skills or filter by schema."""
    skills = registry.list_skills(schema_id)

    return SkillListResponse(
        skills=skills,
        total=len(skills),
        schema_id=schema_id,
    )


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(
    skill_id: str,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    schema_id: Optional[str] = Query(None, description="Schema to search in"),
) -> Skill:
    """Get a specific skill by ID.

    If schema_id is not provided, searches all schemas.
    """
    if schema_id:
        skill = registry.get_skill(schema_id, skill_id)
        if skill:
            return skill
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_id}' not found in schema '{schema_id}'",
        )

    # Search all schemas
    for schema in registry.list_schemas():
        skill = registry.get_skill(schema.schema_id, skill_id)
        if skill:
            return skill

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Skill '{skill_id}' not found",
    )
