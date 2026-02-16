"""Pydantic models package."""

from app.models.events import EventType, GitWebhookPayload, SkillEvent, WebhookPayload
from app.models.execution import (
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
    ValidationResult,
)
from app.models.schema import LoadedSchema, MergeStrategy, SchemaConfig, ValidationRule
from app.models.skill import Skill, SkillConfig, SkillExecutionResult, SkillStatus
from app.models.workflow import (
    LoadedWorkflow,
    OnFailure,
    WorkflowConfig,
    WorkflowDetailResponse,
    WorkflowExecutionMetadata,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionStatus,
    WorkflowListResponse,
    WorkflowStepConfig,
    WorkflowStepResult,
)

__all__ = [
    # Skill models
    "Skill",
    "SkillConfig",
    "SkillStatus",
    "SkillExecutionResult",
    # Schema models
    "SchemaConfig",
    "LoadedSchema",
    "MergeStrategy",
    "ValidationRule",
    # Event models
    "SkillEvent",
    "EventType",
    "WebhookPayload",
    "GitWebhookPayload",
    # Execution models
    "ExecutionRequest",
    "ExecutionResponse",
    "ExecutionStatus",
    "ExecutionMetadata",
    "ValidationResult",
    "TokenUsage",
    # Workflow models
    "OnFailure",
    "WorkflowConfig",
    "WorkflowStepConfig",
    "LoadedWorkflow",
    "WorkflowExecutionRequest",
    "WorkflowStepResult",
    "WorkflowExecutionStatus",
    "WorkflowExecutionMetadata",
    "WorkflowExecutionResponse",
    "WorkflowListResponse",
    "WorkflowDetailResponse",
]
