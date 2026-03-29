"""Pydantic output model for JSON to HTML page generation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HtmlPageResult(BaseModel):
    """Generated HTML page from JSON data."""

    model_config = ConfigDict(populate_by_name=True)

    html_content: str = Field(
        ...,
        alias="htmlContent",
        description="Complete HTML page content starting with <!DOCTYPE html>",
    )
    title: str = Field(
        ...,
        description="Page title derived from the JSON data",
    )
    data_fields_count: Optional[int] = Field(
        None,
        alias="dataFieldsCount",
        description="Number of top-level data fields rendered in the page",
    )

    @field_validator("html_content")
    @classmethod
    def validate_html_content(cls, v: str) -> str:
        """Ensure html_content contains basic HTML structure."""
        if not v or len(v.strip()) < 50:
            raise ValueError("html_content is too short to be a valid HTML page")
        lower = v.strip().lower()
        if not lower.startswith("<!doctype html"):
            raise ValueError("html_content must start with <!DOCTYPE html>")
        return v
