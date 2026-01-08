"""Pydantic output models for example extraction schema."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Document metadata extracted by the metadata skill."""

    title: str = Field(..., description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    date: Optional[str] = Field(None, description="Document date")
    document_type: Optional[str] = Field(None, alias="documentType")


class DocumentSummary(BaseModel):
    """Summary extracted by the summary skill."""

    summary: str = Field(..., description="Brief document summary")
    key_points: List[str] = Field(
        default_factory=list, alias="keyPoints", description="Key points from document"
    )


class Person(BaseModel):
    """Person entity."""

    name: str
    role: Optional[str] = None


class Organization(BaseModel):
    """Organization entity."""

    name: str
    type: Optional[str] = None


class Location(BaseModel):
    """Location entity."""

    name: str
    type: Optional[str] = None  # city, country, address, etc.


class ExtractedEntities(BaseModel):
    """Named entities extracted by the entities skill."""

    people: List[Person] = Field(default_factory=list)
    organizations: List[Organization] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Complete extraction result combining all skills.

    This is the output_model referenced in schema.json.
    """

    # From metadata skill
    title: str
    author: Optional[str] = None
    date: Optional[str] = None
    document_type: Optional[str] = Field(None, alias="documentType")

    # From summary skill
    summary: str
    key_points: List[str] = Field(default_factory=list, alias="keyPoints")

    # From entities skill
    people: List[Person] = Field(default_factory=list)
    organizations: List[Organization] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True
