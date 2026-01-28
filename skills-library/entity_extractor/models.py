"""Pydantic output models for named entity extraction."""

from typing import List, Optional

from pydantic import BaseModel, Field


class Person(BaseModel):
    """Person entity."""

    name: str
    role: Optional[str] = None


class Organization(BaseModel):
    """Organization entity."""

    name: str
    type: Optional[str] = None  # company, government, NGO, etc.


class Location(BaseModel):
    """Location entity."""

    name: str
    type: Optional[str] = None  # city, country, address, region


class EntityResult(BaseModel):
    """Extracted named entities from document."""

    people: List[Person] = Field(default_factory=list, description="People mentioned")
    organizations: List[Organization] = Field(
        default_factory=list, description="Organizations mentioned"
    )
    locations: List[Location] = Field(default_factory=list, description="Locations mentioned")
    dates: List[str] = Field(default_factory=list, description="Dates and time references")
