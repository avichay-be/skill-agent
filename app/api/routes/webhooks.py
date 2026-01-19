"""Webhook API routes for Git events."""

import hashlib
import hmac
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.models.events import GitWebhookPayload, SkillEvent
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookResponse(BaseModel):
    """Response from webhook processing."""

    status: str
    message: str
    affected_schemas: List[str] = []
    new_commit: Optional[str] = None


def verify_github_signature(
    payload: bytes,
    signature: str | None,
    secret: str | None,
) -> bool:
    """Verify GitHub webhook signature.

    Args:
        payload: Raw request body.
        signature: X-Hub-Signature-256 header value.
        secret: Webhook secret.

    Returns:
        True if signature is valid or verification is disabled.
    """
    if not secret:
        # Verification disabled
        return True

    if not signature:
        return False

    # GitHub sends signature as "sha256=<hex>"
    if signature.startswith("sha256="):
        signature = signature[7:]

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


@router.post("/git", response_model=WebhookResponse)
async def handle_git_webhook(
    request: Request,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
) -> WebhookResponse:
    """Handle incoming Git webhook (GitHub/GitLab push events).

    This endpoint receives notifications when skills are updated in Git
    and reloads affected schemas.
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if secret is configured
    if not verify_github_signature(body, x_hub_signature_256, settings.webhook_secret):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse payload
    try:
        payload_data = await request.json()
        payload = GitWebhookPayload(**payload_data)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {e}",
        )

    # Check if this is the branch we care about
    branch = payload.get_branch()
    if branch and branch != settings.github_branch:
        logger.info(f"Ignoring push to branch '{branch}', watching '{settings.github_branch}'")
        return WebhookResponse(
            status="ignored",
            message=f"Push to '{branch}' ignored, watching '{settings.github_branch}'",
        )

    # Get changed files
    changed_files = payload.get_changed_files()
    logger.info(f"Webhook received: {len(changed_files)} files changed in {payload.after}")

    if not changed_files:
        return WebhookResponse(
            status="success",
            message="No file changes detected",
            new_commit=payload.after,
        )

    # Reload affected schemas
    try:
        affected = registry.reload_affected_schemas(changed_files)

        if affected:
            logger.info(f"Reloaded schemas: {affected}")
            return WebhookResponse(
                status="success",
                message=f"Reloaded {len(affected)} schema(s)",
                affected_schemas=affected,
                new_commit=registry.current_commit,
            )
        else:
            return WebhookResponse(
                status="success",
                message="No skill schemas affected by changes",
                new_commit=registry.current_commit,
            )

    except Exception as e:
        logger.exception(f"Failed to process webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload schemas: {e}",
        )


@router.post("/reload", response_model=WebhookResponse)
async def force_reload(
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> WebhookResponse:
    """Force reload all skills from Git.

    This is a manual trigger endpoint, useful for:
    - Initial loading
    - Recovery from errors
    - Testing
    """
    try:
        new_commit = registry.reload()

        return WebhookResponse(
            status="success",
            message=f"Reloaded {registry.schemas_count} schema(s) with {registry.skills_count} skills",
            affected_schemas=[s.schema_id for s in registry.list_schemas()],
            new_commit=new_commit,
        )

    except Exception as e:
        logger.exception(f"Failed to reload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload: {e}",
        )


@router.get("/events")
async def get_recent_events(
    registry: Annotated[SkillRegistry, Depends(get_registry)],
    limit: int = 50,
) -> List[SkillEvent]:
    """Get recent events from the registry."""
    return registry.get_recent_events(limit)
