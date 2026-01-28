"""Skill-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    """Skill availability status."""

    ACTIVE = "active"
    DISABLED = "disabled"
    DRAFT = "draft"


class SkillConfig(BaseModel):
    """Individual skill configuration from schema.json."""

    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    prompt_file: str = Field(..., description="Relative path to prompt .md file")
    parallel_group: int = Field(
        default=1, description="Execution order grouping (lower runs first)"
    )
    timeout_seconds: int = Field(default=45, description="Max execution time")
    retry_count: int = Field(default=2, description="Number of retries on failure")
    output_fields: List[str] = Field(default_factory=list, description="Fields this skill extracts")
    vendor: Optional[str] = Field(default=None, description="Preferred LLM vendor")
    model: Optional[str] = Field(default=None, description="Preferred model")
    temperature: float = Field(default=0.0, description="LLM temperature")
    status: SkillStatus = Field(default=SkillStatus.ACTIVE, description="Skill status")


class Skill(BaseModel):
    """Loaded skill with prompt content."""

    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    prompt: str = Field(..., description="Actual prompt content from .md file")
    config: SkillConfig = Field(..., description="Skill configuration")
    schema_id: str = Field(..., description="Parent schema identifier")
    version: str = Field(..., description="Git commit SHA or version")
    file_path: str = Field(..., description="Path to prompt file")
    loaded_at: datetime = Field(default_factory=datetime.utcnow)

    def get_effective_vendor(self, default: str) -> str:
        """Get vendor, falling back to default."""
        return self.config.vendor or default

    def get_effective_model(self, default: Optional[str]) -> Optional[str]:
        """Get model, falling back to default."""
        return self.config.model or default


class SkillExecutionResult(BaseModel):
    """Result from executing a single skill."""

    skill_id: str = Field(..., description="Executed skill identifier")
    success: bool = Field(..., description="Whether execution succeeded")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Token consumption")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    model_used: str = Field(..., description="Model that was used")
    vendor_used: str = Field(..., description="Vendor that was used")
    retries: int = Field(default=0, description="Number of retries needed")


class SkillListResponse(BaseModel):
    """Response for listing skills."""

    skills: List[Skill] = Field(default_factory=list)
    total: int = Field(default=0)
    schema_id: Optional[str] = Field(default=None)
