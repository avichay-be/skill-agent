"""FastAPI application entry point."""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import admin, execute, schemas, skills, webhooks, workflows
from app.core.config import get_settings
from app.core.exceptions import SkillAgentError, skill_agent_exception_handler
from app.core.middleware import RequestIDLogFilter, RequestIDMiddleware, TimeoutMiddleware
from app.core.rate_limiter import limiter
from app.services.skill_registry import SkillRegistry


class _JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include any extra keys the caller passed
        for key in ("execution_id", "schema_id", "duration_ms", "total_tokens", "skills_count"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


def _configure_logging(debug: bool) -> None:
    """Set up logging: structured JSON in production, human-readable in dev."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any existing handlers so we do not duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.addFilter(RequestIDLogFilter())

    if debug:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s")
        )
    else:
        handler.setFormatter(_JSONFormatter())

    root.addHandler(handler)


# Defer full logging configuration until create_app() where we know the debug flag.
# A basic config lets import-time log calls still work.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}")

    # Initialize registry on startup if local path is configured
    if settings.local_skills_path or settings.github_repo_url or Path("./skills-library").exists():
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

    if settings.enable_cosmosdb:
        logger.info("CosmosDB integration is temporarily disabled; skipping initialization")

    yield

    # Cleanup
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Reconfigure logging now that settings are available
    _configure_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        description="Event-driven skill loader and executor for LLM-based document extraction",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add request ID middleware (outermost so all downstream middleware sees it)
    app.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

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
