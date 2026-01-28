"""Admin API routes for system management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.security import ApiKeyDep
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    registry_initialized: bool
    schemas_count: int
    skills_count: int
    current_commit: str | None


class InitializeResponse(BaseModel):
    """Initialize response."""

    status: str
    message: str
    schemas_loaded: int
    skills_loaded: int
    git_commit: str | None


@router.get("/health", response_model=HealthResponse)
async def health_check(
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> HealthResponse:
    """Check service health and registry status."""
    return HealthResponse(
        status="healthy",
        registry_initialized=registry.schemas_count > 0,
        schemas_count=registry.schemas_count,
        skills_count=registry.skills_count,
        current_commit=registry.current_commit,
    )


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_registry(
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InitializeResponse:
    """Initialize or reinitialize the skill registry.

    This loads skills from the configured Git repository or local path.
    """
    try:
        commit = registry.initialize()

        return InitializeResponse(
            status="success",
            message="Registry initialized successfully",
            schemas_loaded=registry.schemas_count,
            skills_loaded=registry.skills_count,
            git_commit=commit,
        )

    except Exception as e:
        logger.exception(f"Failed to initialize registry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize: {e}",
        )


@router.post("/reload", response_model=InitializeResponse)
async def reload_registry(
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> InitializeResponse:
    """Reload all skills from Git (pull latest changes)."""
    try:
        commit = registry.reload()

        return InitializeResponse(
            status="success",
            message="Registry reloaded successfully",
            schemas_loaded=registry.schemas_count,
            skills_loaded=registry.skills_count,
            git_commit=commit,
        )

    except Exception as e:
        logger.exception(f"Failed to reload registry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload: {e}",
        )


@router.get("/config")
async def get_config(
    _api_key: ApiKeyDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """Get current configuration (non-sensitive values only)."""
    return {
        "app_name": settings.app_name,
        "debug": settings.debug,
        "github_repo_url": settings.github_repo_url or "(not configured)",
        "github_branch": settings.github_branch,
        "skills_base_path": settings.skills_base_path,
        "local_skills_path": settings.local_skills_path or "(not configured)",
        "default_vendor": settings.default_vendor,
        "default_timeout_seconds": settings.default_timeout_seconds,
        "default_retry_count": settings.default_retry_count,
        "max_parallel_skills": settings.max_parallel_skills,
        "anthropic_configured": bool(settings.anthropic_api_key),
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.google_api_key),
    }
