"""Custom exceptions and exception handlers."""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class SkillAgentError(Exception):
    """Base exception for Skill Agent."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SchemaNotFoundError(SkillAgentError):
    """Schema not found."""

    def __init__(self, schema_id: str):
        super().__init__(
            f"Schema '{schema_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class SkillNotFoundError(SkillAgentError):
    """Skill not found."""

    def __init__(self, skill_id: str, schema_id: str | None = None):
        msg = f"Skill '{skill_id}' not found"
        if schema_id:
            msg += f" in schema '{schema_id}'"
        super().__init__(msg, status_code=status.HTTP_404_NOT_FOUND)


class RegistryNotInitializedError(SkillAgentError):
    """Registry not initialized."""

    def __init__(self):
        super().__init__(
            "Skill registry not initialized. Call /admin/reload first.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ExecutionError(SkillAgentError):
    """Execution failed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def skill_agent_exception_handler(
    request: Request, exc: SkillAgentError
) -> JSONResponse:
    """Handle SkillAgentError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "type": type(exc).__name__},
    )
