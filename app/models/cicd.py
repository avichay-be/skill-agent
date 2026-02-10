"""CI/CD pipeline subagent Pydantic models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ChangeCategory(str, Enum):
    """Categories of code changes detected."""

    APP_CODE = "app_code"
    DEPENDENCIES = "dependencies"
    INFRASTRUCTURE = "infrastructure"
    CI_CD = "ci_cd"
    TESTS = "tests"
    DOCS = "docs"
    CONFIG = "config"


class RiskLevel(str, Enum):
    """Risk level of changes."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PipelineFileType(str, Enum):
    """Types of pipeline files that can be generated/updated."""

    GITHUB_ACTIONS = "github_actions"
    DOCKERFILE = "dockerfile"
    BICEP = "bicep"
    DEPLOY_SCRIPT = "deploy_script"


class CICDExecutionStatus(str, Enum):
    """Status of a CI/CD pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"


class CICDWebhookRequest(BaseModel):
    """Incoming webhook request for CI/CD push events."""

    ref: str = Field(..., description="Git ref (e.g., refs/heads/main)")
    before: str = Field(..., description="Previous commit SHA")
    after: str = Field(..., description="New commit SHA")
    repository: Dict[str, Any] = Field(..., description="Repository info")
    commits: List[Dict[str, Any]] = Field(default_factory=list, description="List of commits")
    sender: Optional[Dict[str, Any]] = Field(default=None, description="User who pushed")

    def get_branch(self) -> Optional[str]:
        """Extract branch name from ref."""
        if self.ref.startswith("refs/heads/"):
            return self.ref.removeprefix("refs/heads/")
        return None

    def get_repo_full_name(self) -> str:
        """Get owner/repo format."""
        return str(self.repository.get("full_name", ""))

    def get_changed_files(self) -> List[str]:
        """Get deduplicated list of all changed files."""
        files: set[str] = set()
        for commit in self.commits:
            files.update(commit.get("added", []))
            files.update(commit.get("modified", []))
            files.update(commit.get("removed", []))
        return sorted(files)


class FileChange(BaseModel):
    """A single file change in the diff."""

    path: str = Field(..., description="File path")
    status: str = Field(..., description="added, modified, or removed")
    patch: Optional[str] = Field(default=None, description="Diff patch content")


class ChangeAnalysis(BaseModel):
    """LLM-generated analysis of code changes."""

    categories: List[ChangeCategory] = Field(
        default_factory=list, description="What types of changes were made"
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Overall risk assessment")
    summary: str = Field(default="", description="Human-readable summary of changes")
    affected_services: List[str] = Field(
        default_factory=list, description="Services affected by changes"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Recommended pipeline actions"
    )
    pipeline_files_to_update: List[PipelineFileType] = Field(
        default_factory=list, description="Which pipeline files need updating"
    )


class PipelineFileUpdate(BaseModel):
    """A generated or updated pipeline file."""

    file_type: PipelineFileType = Field(..., description="Type of pipeline file")
    file_path: str = Field(..., description="Path in the repository")
    content: str = Field(..., description="File content")
    reason: str = Field(default="", description="Why this file was updated")


class SecurityFinding(BaseModel):
    """A security issue found during validation."""

    severity: str = Field(..., description="low, medium, high, critical")
    message: str = Field(..., description="Description of the finding")
    file_path: str = Field(default="", description="File where issue was found")
    line: Optional[int] = Field(default=None, description="Line number if applicable")


class PipelineValidationResult(BaseModel):
    """Result of validating generated pipeline files."""

    valid: bool = Field(default=True, description="Whether all files passed validation")
    yaml_errors: List[str] = Field(default_factory=list, description="YAML syntax errors")
    dockerfile_errors: List[str] = Field(default_factory=list, description="Dockerfile issues")
    security_findings: List[SecurityFinding] = Field(
        default_factory=list, description="Security issues found"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warnings")


class CICDExecutionResponse(BaseModel):
    """Response from CI/CD pipeline execution."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    status: CICDExecutionStatus = Field(..., description="Execution status")
    repository: str = Field(default="", description="Repository full name")
    branch: str = Field(default="", description="Branch that triggered the pipeline")
    commit_sha: str = Field(default="", description="Commit SHA that triggered the pipeline")
    analysis: Optional[ChangeAnalysis] = Field(default=None, description="Change analysis")
    generated_files: List[PipelineFileUpdate] = Field(
        default_factory=list, description="Generated/updated pipeline files"
    )
    validation: Optional[PipelineValidationResult] = Field(
        default=None, description="Validation result"
    )
    pr_url: Optional[str] = Field(default=None, description="URL of created PR")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
