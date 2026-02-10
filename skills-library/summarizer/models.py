"""Pydantic output model for document summarization."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class SummaryResult(BaseModel):
    """Generated document summary."""

    model_config = ConfigDict(populate_by_name=True)

    summary: str = Field(..., description="Brief 2-4 sentence summary")
    key_points: List[str] = Field(
        default_factory=list, alias="keyPoints", description="3-7 key takeaways from the document"
    )
