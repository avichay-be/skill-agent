"""Execution-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Status of an extraction execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some skills succeeded, some failed


class ExecutionRequest(BaseModel):
    """Request to execute extraction on a document."""

    document: str = Field(..., description="Document content to extract from")
    skill_name: str = Field(..., description="Skill name (schema_id) to execute")
    vendor: Optional[str] = Field(default=None, description="Override default LLM vendor")
    model: Optional[str] = Field(default=None, description="Override default model")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Additional execution options"
    )


class ValidationResult(BaseModel):
    """Result of validation checks."""

    status: str = Field(..., description="PASS, REVIEW, or FAIL")
    quality_score: int = Field(default=100, description="Quality score 0-100")
    checks: List[Dict[str, Any]] = Field(
        default_factory=list, description="Individual check results"
    )
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TokenUsage(BaseModel):
    """Token usage tracking."""

    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)


class ExecutionMetadata(BaseModel):
    """Metadata about the extraction execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    processing_time_ms: Optional[int] = Field(default=None)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    token_usage_by_skill: Dict[str, TokenUsage] = Field(default_factory=dict)
    models_used: List[str] = Field(default_factory=list)
    vendors_used: List[str] = Field(default_factory=list)
    git_commit: Optional[str] = Field(default=None)
    schema_version: Optional[str] = Field(default=None)


class ExecutionResponse(BaseModel):
    """Response from extraction execution."""

    status: ExecutionStatus = Field(..., description="Execution status")
    skill_name: str = Field(..., description="Skill name used")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Extracted data")
    validation: Optional[ValidationResult] = Field(default=None)
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
    skill_results: List["SkillExecutionResult"] = Field(
        default_factory=list, description="Individual skill results"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")


# Import to avoid circular dependency
from app.models.skill import SkillExecutionResult  # noqa: E402

ExecutionResponse.model_rebuild()
