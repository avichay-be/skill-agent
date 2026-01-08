"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, execute, schemas, skills, webhooks
from app.core.config import get_settings
from app.core.exceptions import SkillAgentError, skill_agent_exception_handler
from app.services.skill_registry import SkillRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}")

    # Initialize registry on startup if local path is configured
    if settings.local_skills_path or settings.github_repo_url:
        try:
            registry = SkillRegistry()
            commit = registry.initialize()
            logger.info(
                f"Registry initialized: {registry.schemas_count} schemas, "
                f"{registry.skills_count} skills (commit: {commit[:8] if commit != 'local' else 'local'})"
            )
        except Exception as e:
            logger.warning(f"Failed to auto-initialize registry: {e}")
            logger.info("Call POST /api/v1/admin/initialize to manually initialize")

    yield

    # Cleanup
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Event-driven skill loader and executor for LLM-based document extraction",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(SkillAgentError, skill_agent_exception_handler)

    # Register routers
    api_prefix = "/api/v1"
    app.include_router(admin.router, prefix=api_prefix)
    app.include_router(skills.router, prefix=api_prefix)
    app.include_router(schemas.router, prefix=api_prefix)
    app.include_router(execute.router, prefix=api_prefix)
    app.include_router(webhooks.router, prefix=api_prefix)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": settings.app_name,
            "version": "0.1.0",
            "docs": "/docs",
        }

    # Generic error handler
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    import sys
    import os

    # Add parent directory to path for proper module imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        loop="asyncio",  # Use asyncio instead of uvloop to avoid multiprocessing issues
    )
