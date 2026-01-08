"""Event-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events emitted by the skill loader."""

    # Skill events
    SKILL_CREATED = "skill.created"
    SKILL_UPDATED = "skill.updated"
    SKILL_DELETED = "skill.deleted"
    SKILL_ENABLED = "skill.enabled"
    SKILL_DISABLED = "skill.disabled"

    # Schema events
    SCHEMA_CREATED = "schema.created"
    SCHEMA_UPDATED = "schema.updated"
    SCHEMA_DELETED = "schema.deleted"
    SCHEMA_RELOADED = "schema.reloaded"

    # Execution events
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"

    # System events
    REGISTRY_RELOADED = "registry.reloaded"
    GIT_SYNC_COMPLETED = "git.sync.completed"
    GIT_SYNC_FAILED = "git.sync.failed"


class SkillEvent(BaseModel):
    """Event emitted when skills or schemas change."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType = Field(..., description="Event type")
    schema_id: Optional[str] = Field(default=None, description="Affected schema")
    skill_id: Optional[str] = Field(default=None, description="Affected skill")
    git_commit: Optional[str] = Field(default=None, description="Git commit SHA")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict, description="Additional data")


class WebhookPayload(BaseModel):
    """Payload sent to registered outbound webhooks."""

    event: SkillEvent = Field(..., description="The event that occurred")
    source: str = Field(default="skill-agent", description="Source service")
    api_version: str = Field(default="v1", description="API version")


class GitWebhookPayload(BaseModel):
    """Payload received from GitHub/GitLab webhooks."""

    ref: Optional[str] = Field(default=None, description="Git ref (e.g., refs/heads/main)")
    before: Optional[str] = Field(default=None, description="Previous commit SHA")
    after: Optional[str] = Field(default=None, description="New commit SHA")
    commits: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of commits"
    )
    repository: Optional[Dict[str, Any]] = Field(
        default=None, description="Repository info"
    )

    def get_branch(self) -> Optional[str]:
        """Extract branch name from ref."""
        if self.ref and self.ref.startswith("refs/heads/"):
            return self.ref.replace("refs/heads/", "")
        return None

    def get_changed_files(self) -> List[str]:
        """Get list of all changed files from commits."""
        files = set()
        for commit in self.commits:
            files.update(commit.get("added", []))
            files.update(commit.get("modified", []))
            files.update(commit.get("removed", []))
        return list(files)
