from pydantic import BaseModel, Field
from typing import Optional


class HelloWorldResult(BaseModel):
    """Output model for Hello World skill."""

    greeting: str = Field(..., description="The greeting message extracted from the document")
    message: Optional[str] = Field(None, description="Additional message or context")

    class Config:
        populate_by_name = True
