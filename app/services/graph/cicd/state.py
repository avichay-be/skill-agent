"""
LangGraph state schema for CI/CD pipeline execution.

This module defines the state that flows through the CI/CD LangGraph subgraph.
"""

from datetime import datetime, timezone
from operator import add
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.cicd import (
    ChangeAnalysis,
    CICDExecutionStatus,
    FileChange,
    PipelineFileUpdate,
    PipelineValidationResult,
)


class CICDGraphState(BaseModel):
    """State that flows through the CI/CD LangGraph execution.

    Uses Annotated types with reducers for proper state merging.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ===== Input Data =====
    execution_id: str = Field(..., description="Unique execution identifier")
    repository: str = Field(..., description="Repository full name (owner/repo)")
    branch: str = Field(..., description="Branch that triggered the pipeline")
    before_sha: str = Field(..., description="Previous commit SHA")
    after_sha: str = Field(..., description="New commit SHA")
    github_token: str = Field(..., description="GitHub token for API calls")

    # ===== Fetched Data =====
    file_changes: List[FileChange] = Field(
        default_factory=list, description="Files changed in the push"
    )
    existing_pipeline_files: Dict[str, Optional[str]] = Field(
        default_factory=dict, description="Current pipeline file contents"
    )

    # ===== Analysis =====
    analysis: Optional[ChangeAnalysis] = Field(
        None, description="LLM analysis of changes"
    )

    # ===== Generated Files =====
    generated_files: Annotated[List[PipelineFileUpdate], add] = Field(
        default_factory=list, description="Generated/updated pipeline files"
    )

    # ===== Validation =====
    validation: Optional[PipelineValidationResult] = Field(
        None, description="Validation result for generated files"
    )

    # ===== PR =====
    pr_url: Optional[str] = Field(None, description="URL of created PR")
    pr_branch: Optional[str] = Field(None, description="Branch name for the PR")

    # ===== Control Flow =====
    next_action: Optional[str] = Field(None, description="Next action to take")
    status: CICDExecutionStatus = Field(
        default=CICDExecutionStatus.PENDING, description="Execution status"
    )

    # ===== Metadata =====
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # ===== Errors & Progress =====
    errors: Annotated[List[str], add] = Field(
        default_factory=list, description="Accumulated errors"
    )
    progress_events: Annotated[List[Dict[str, Any]], add] = Field(
        default_factory=list, description="Progress events for streaming"
    )
