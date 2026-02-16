"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import admin, execute, schemas, skills, webhooks, workflows
from app.core.config import get_settings
from app.core.exceptions import SkillAgentError, skill_agent_exception_handler
from app.core.rate_limiter import limiter
from app.services.cosmosdb import close_cosmosdb_service, initialize_cosmosdb_service
from app.services.skill_registry import SkillRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request timeout."""

    def __init__(self, app: FastAPI, timeout_seconds: int = 300) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        """Process request with timeout tracking."""
        import asyncio

        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": "Request timeout",
                    "detail": f"Request exceeded {self.timeout_seconds} seconds",
                },
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
                f"{registry.skills_count} skills, "
                f"{registry.workflows_count} workflows "
                f"(commit: {commit[:8] if commit != 'local' else 'local'})"
            )
        except Exception as e:
            logger.warning(f"Failed to auto-initialize registry: {e}")
            logger.info("Call POST /api/v1/admin/initialize to manually initialize")

    # Initialize CosmosDB if enabled
    if settings.enable_cosmosdb:
        try:
            await initialize_cosmosdb_service()
        except Exception as e:
            logger.warning(f"Failed to initialize CosmosDB: {e}")

    yield

    # Cleanup
    if settings.enable_cosmosdb:
        await close_cosmosdb_service()
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

    # Add timeout middleware (must be added before other middleware)
    app.add_middleware(TimeoutMiddleware, timeout_seconds=settings.request_timeout_seconds)  # type: ignore[arg-type]

    # Add CORS middleware with environment-based origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add rate limiter to app state
    app.state.limiter = limiter

    # Register exception handlers
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SkillAgentError, skill_agent_exception_handler)  # type: ignore[arg-type]

    # Register routers
    api_prefix = "/api/v1"
    app.include_router(admin.router, prefix=api_prefix)
    app.include_router(skills.router, prefix=api_prefix)
    app.include_router(schemas.router, prefix=api_prefix)
    app.include_router(execute.router, prefix=api_prefix)
    app.include_router(webhooks.router, prefix=api_prefix)
    app.include_router(workflows.router, prefix=api_prefix)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": "0.1.0",
            "docs": "/docs",
        }

    # Health check endpoint
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint for container orchestration."""
        return {"status": "healthy", "service": settings.app_name}

    # Generic error handler
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Always log full exception details server-side
        logger.exception(f"Unhandled exception: {exc}")

        # In production (debug=False), hide internal error details from clients
        if settings.debug:
            detail = str(exc)
        else:
            detail = "An unexpected error occurred. Please try again later."

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "detail": detail},
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import os
    import sys

    import uvicorn

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
