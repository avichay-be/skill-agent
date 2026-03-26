"""Execution-related Pydantic models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
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
    vendor: str | None = Field(default=None, description="Override default LLM vendor")
    model: str | None = Field(default=None, description="Override default model")
    options: dict[str, Any] = Field(
        default_factory=dict, description="Additional execution options"
    )
    save_to_cosmos: bool = Field(default=False, description="Whether to persist result to CosmosDB")


class DocumentItem(BaseModel):
    """A single document in a batch request."""

    id: str = Field(..., description="Caller's document identifier")
    content: str = Field(..., description="Document text content")


class BatchExecutionRequest(BaseModel):
    """Request to execute extraction on multiple documents via Anthropic Batch API."""

    documents: list[DocumentItem] = Field(..., description="Documents to process")
    skill_name: str = Field(..., description="Schema ID to execute")
    vendor: str | None = Field(default=None, description="Override LLM vendor (must be anthropic)")
    model: str | None = Field(default=None, description="Override default model")


class ValidationResult(BaseModel):
    """Result of validation checks."""

    status: str = Field(..., description="PASS, REVIEW, or FAIL")
    quality_score: int = Field(default=100, description="Quality score 0-100")
    checks: list[dict[str, Any]] = Field(
        default_factory=list, description="Individual check results"
    )
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TokenUsage(BaseModel):
    """Token usage tracking."""

    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)


class ExecutionMetadata(BaseModel):
    """Metadata about the extraction execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    processing_time_ms: int | None = Field(default=None)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    token_usage_by_skill: dict[str, TokenUsage] = Field(default_factory=dict)
    models_used: list[str] = Field(default_factory=list)
    vendors_used: list[str] = Field(default_factory=list)
    git_commit: str | None = Field(default=None)
    schema_version: str | None = Field(default=None)


class ExecutionResponse(BaseModel):
    """Response from extraction execution."""

    status: ExecutionStatus = Field(..., description="Execution status")
    skill_name: str = Field(..., description="Skill name used")
    data: dict[str, Any] | None = Field(default=None, description="Extracted data")
    validation: ValidationResult | None = Field(default=None)
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
    skill_results: list["SkillExecutionResult"] = Field(
        default_factory=list, description="Individual skill results"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class BatchStatus(str, Enum):
    """Status of a batch execution."""

    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELING = "canceling"
    EXPIRED = "expired"


class BatchExecutionResponse(BaseModel):
    """Response from batch extraction execution."""

    batch_id: str = Field(..., description="Anthropic batch ID")
    status: BatchStatus = Field(..., description="Batch processing status")
    total_documents: int = Field(..., description="Number of documents in batch")
    results: dict[str, ExecutionResponse] | None = Field(
        default=None, description="Results keyed by document ID (when completed)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    request_counts: dict[str, int] | None = Field(
        default=None, description="Anthropic batch request counts"
    )


# Import to avoid circular dependency
from app.models.skill import SkillExecutionResult  # noqa: E402

ExecutionResponse.model_rebuild()
