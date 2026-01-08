"""Pydantic output model for document summarization."""

from typing import List
from pydantic import BaseModel, Field


class SummaryResult(BaseModel):
    """Generated document summary."""

    summary: str = Field(..., description="Brief 2-4 sentence summary")
    key_points: List[str] = Field(
        default_factory=list,
        alias="keyPoints",
        description="3-7 key takeaways from the document"
    )

    class Config:
        populate_by_name = True
