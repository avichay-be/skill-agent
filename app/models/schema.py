"""Schema-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


class MergeStrategy(str, Enum):
    """Strategy for merging skill outputs."""

    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    MERGE_DEEP = "merge_deep"


class ValidationRule(BaseModel):
    """Validation rule for post-processing."""

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    type: str = Field(..., description="Rule type: sum_check, range_check, required, etc.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")
    severity: str = Field(default="error", description="error or warning")


class PostProcessing(BaseModel):
    """Post-processing configuration."""

    merge_strategy: MergeStrategy = Field(
        default=MergeStrategy.MERGE_DEEP, description="How to merge skill outputs"
    )
    validation_rules: List[ValidationRule] = Field(
        default_factory=list, description="Validation rules to apply"
    )


class SchemaConfig(BaseModel):
    """Schema orchestration configuration loaded from schema.json."""

    schema_id: str = Field(..., description="Unique schema identifier")
    version: str = Field(..., description="Schema version")
    name: str = Field(..., description="Human-readable schema name")
    description: Optional[str] = Field(default=None, description="Schema description")
    output_model: Optional[str] = Field(
        default=None, description="Python path to Pydantic output model"
    )
    skills: List["SkillConfig"] = Field(
        default_factory=list, description="Skill configurations"
    )
    post_processing: PostProcessing = Field(
        default_factory=PostProcessing, description="Post-processing config"
    )


# Import here to avoid circular import
from app.models.skill import Skill, SkillConfig  # noqa: E402

SchemaConfig.model_rebuild()


class LoadedSchema(BaseModel):
    """Fully loaded schema with skills and output model."""

    config: SchemaConfig = Field(..., description="Schema configuration")
    skills: Dict[str, Skill] = Field(
        default_factory=dict, description="Loaded skills keyed by skill_id"
    )
    output_model: Optional[Type[BaseModel]] = Field(
        default=None, description="Dynamically loaded Pydantic output model"
    )
    git_commit: str = Field(..., description="Git commit SHA")
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
    source_path: str = Field(..., description="Path to schema directory")

    model_config = {"arbitrary_types_allowed": True}

    def get_skills_by_group(self) -> Dict[int, List[Skill]]:
        """Group skills by parallel_group for ordered execution."""
        groups: Dict[int, List[Skill]] = {}
        for skill in self.skills.values():
            group = skill.config.parallel_group
            if group not in groups:
                groups[group] = []
            groups[group].append(skill)
        return dict(sorted(groups.items()))

    def get_active_skills(self) -> List[Skill]:
        """Get only active skills."""
        from app.models.skill import SkillStatus

        return [s for s in self.skills.values() if s.config.status == SkillStatus.ACTIVE]


class SchemaListResponse(BaseModel):
    """Response for listing schemas."""

    schemas: List[SchemaConfig] = Field(default_factory=list)
    total: int = Field(default=0)


class SchemaDetailResponse(BaseModel):
    """Detailed schema response with skills."""

    schema_config: SchemaConfig = Field(..., alias="schema")
    skills: List[Skill] = Field(default_factory=list)
    git_commit: str
    loaded_at: datetime

    model_config = {"populate_by_name": True}
