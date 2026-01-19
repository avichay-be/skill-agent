"""
LangGraph state schema for skill execution.

This module defines the state that flows through the LangGraph execution graph.
"""

from datetime import datetime
from operator import add
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.execution import TokenUsage, ValidationResult
from app.models.skill import SkillExecutionResult


class SkillGraphState(BaseModel):
    """State that flows through the LangGraph execution.

    This state is passed between nodes and accumulates results.
    Uses Annotated types with reducers for proper state merging.
    """

    # ===== Input Data =====
    document: str = Field(..., description="Original document content")
    schema_id: str = Field(..., description="Schema/skill set to execute")
    execution_id: str = Field(..., description="Unique execution identifier")
    vendor: Optional[str] = Field(None, description="LLM vendor override")
    model: Optional[str] = Field(None, description="Model override")

    # ===== Execution Context =====
    current_group: int = Field(default=1, description="Current parallel group being executed")
    completed_groups: List[int] = Field(default_factory=list, description="Groups that completed")
    pending_skills: List[str] = Field(default_factory=list, description="Skills queued for execution")
    active_skills: List[str] = Field(default_factory=list, description="Skills currently running")

    # ===== Accumulated Results =====
    # Use Annotated with 'add' reducer to append results across nodes
    skill_results: Annotated[List[SkillExecutionResult], add] = Field(
        default_factory=list,
        description="Results from all executed skills"
    )

    # Merged data - updated by merge node
    merged_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Merged output from all skills"
    )

    # ===== Validation & Quality =====
    validation_result: Optional[ValidationResult] = Field(
        None,
        description="Validation result after execution"
    )
    quality_score: int = Field(default=100, description="Overall quality score")

    # ===== Metadata =====
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Cumulative token usage"
    )
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # ===== Control Flow =====
    should_retry: bool = Field(default=False, description="Should retry failed skills")
    retry_count: int = Field(default=0, description="Number of retries performed")
    max_retries: int = Field(default=2, description="Maximum retry attempts")

    human_review_required: bool = Field(default=False, description="Pause for human review")
    human_feedback: Optional[Dict[str, Any]] = Field(None, description="Human reviewer feedback")

    # Dynamic routing
    next_action: Optional[str] = Field(None, description="Next action to take")
    conditional_branches: Dict[str, bool] = Field(
        default_factory=dict,
        description="Conditional branch flags"
    )

    # ===== Error Handling =====
    errors: Annotated[List[str], add] = Field(
        default_factory=list,
        description="Accumulated errors"
    )
    status: str = Field(default="running", description="pending|running|completed|failed|paused")

    # ===== Advanced Features =====
    # For sub-graph support
    sub_executions: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Results from sub-graph executions"
    )

    # For streaming progress
    progress_events: Annotated[List[Dict[str, Any]], add] = Field(
        default_factory=list,
        description="Progress events for streaming"
    )

    class Config:
        arbitrary_types_allowed = True
