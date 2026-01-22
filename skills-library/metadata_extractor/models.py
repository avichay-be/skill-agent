"""Pydantic output model for metadata extraction."""

from typing import Optional

from pydantic import BaseModel, Field


class MetadataResult(BaseModel):
    """Extracted document metadata."""

    title: str = Field(..., description="Document title or main heading")
    author: Optional[str] = Field(None, description="Document author")
    date: Optional[str] = Field(None, description="Document date (ISO format preferred)")
    document_type: Optional[str] = Field(
        None,
        alias="documentType",
        description="Type of document (report, article, memo, contract, etc.)",
    )
    content: Optional[str] = Field(None, description="Full text content of the document")

    class Config:
        populate_by_name = True
