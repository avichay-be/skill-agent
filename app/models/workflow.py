"""Workflow-related Pydantic models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.execution import ExecutionResponse, TokenUsage


class OnFailure(str, Enum):
    """Action to take when a workflow step fails."""

    STOP = "stop"
    CONTINUE = "continue"


class WorkflowStepConfig(BaseModel):
    """Configuration for a single step in a workflow."""

    step_id: str = Field(..., description="Unique step identifier")
    schema_id: str = Field(..., description="Schema to execute for this step")
    name: str = Field(..., description="Human-readable step name")
    description: Optional[str] = Field(default=None, description="Step description")
    on_failure: OnFailure = Field(default=OnFailure.STOP, description="Action on failure")


class WorkflowConfig(BaseModel):
    """Workflow definition loaded from JSON."""

    workflow_id: str = Field(..., description="Unique workflow identifier")
    version: str = Field(..., description="Workflow version")
    name: str = Field(..., description="Human-readable workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    steps: List[WorkflowStepConfig] = Field(
        ..., min_length=1, description="Ordered list of workflow steps"
    )


class LoadedWorkflow(BaseModel):
    """A workflow loaded into the registry."""

    config: WorkflowConfig = Field(..., description="Workflow configuration")
    git_commit: str = Field(..., description="Git commit SHA when loaded")
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_path: str = Field(..., description="Path to workflow JSON file")


class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow."""

    document: str = Field(..., description="Document content to process")
    workflow_id: str = Field(..., description="Workflow ID to execute")
    vendor: Optional[str] = Field(default=None, description="Override default LLM vendor")
    model: Optional[str] = Field(default=None, description="Override default model")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Additional execution options"
    )


class WorkflowStepResult(BaseModel):
    """Result of a single workflow step."""

    step_id: str = Field(..., description="Step identifier")
    schema_id: str = Field(..., description="Schema that was executed")
    step_index: int = Field(..., description="Zero-based step index")
    execution_response: ExecutionResponse = Field(..., description="Full execution response")


class WorkflowExecutionStatus(str, Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class WorkflowExecutionMetadata(BaseModel):
    """Metadata about a workflow execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str = Field(..., description="Workflow that was executed")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)
    processing_time_ms: Optional[int] = Field(default=None)
    total_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    steps_completed: int = Field(default=0)
    steps_total: int = Field(default=0)
    git_commit: Optional[str] = Field(default=None)


class WorkflowExecutionResponse(BaseModel):
    """Response from workflow execution."""

    status: WorkflowExecutionStatus = Field(..., description="Workflow execution status")
    workflow_id: str = Field(..., description="Workflow that was executed")
    workflow_name: str = Field(..., description="Workflow display name")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Output data from the last successful step"
    )
    metadata: WorkflowExecutionMetadata = Field(
        default_factory=lambda: WorkflowExecutionMetadata(workflow_id="")
    )
    step_results: List[WorkflowStepResult] = Field(
        default_factory=list, description="Results from each step"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")


class WorkflowListResponse(BaseModel):
    """Response for listing workflows."""

    workflows: List[WorkflowConfig] = Field(default_factory=list)
    total: int = Field(default=0)


class WorkflowDetailResponse(BaseModel):
    """Detailed workflow response with validation status."""

    workflow: WorkflowConfig = Field(..., description="Workflow configuration")
    git_commit: str = Field(..., description="Git commit SHA")
    loaded_at: datetime = Field(..., description="When the workflow was loaded")
    schemas_valid: bool = Field(..., description="Whether all referenced schemas exist")
    missing_schemas: List[str] = Field(
        default_factory=list, description="Schemas referenced but not found"
    )
