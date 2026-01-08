"""Security utilities - API key authentication."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Validate API key from header.

    Args:
        api_key: API key from X-API-Key header.
        settings: Application settings.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if not api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    if api_key not in settings.api_keys:
        logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key


# Type alias for dependency injection
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
