"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# Set test environment before importing app modules
os.environ["API_KEYS"] = "test-api-key"
os.environ["LOCAL_SKILLS_PATH"] = ""
os.environ["GITHUB_REPO_URL"] = ""


@pytest.fixture
def test_api_key() -> str:
    """Test API key."""
    return "test-api-key"


@pytest.fixture
def temp_skills_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with test skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_path = Path(tmpdir) / "skills"
        skills_path.mkdir()

        # Create example schema
        schema_dir = skills_path / "test_schema"
        schema_dir.mkdir()
        prompts_dir = schema_dir / "prompts"
        prompts_dir.mkdir()

        # Write schema.json
        schema_json = schema_dir / "schema.json"
        schema_json.write_text("""
{
    "schema_id": "test_schema",
    "version": "1.0.0",
    "name": "Test Schema",
    "description": "A test schema for unit tests",
    "skills": [
        {
            "id": "skill_1",
            "name": "Test Skill 1",
            "prompt_file": "prompts/skill_1.md",
            "parallel_group": 1,
            "timeout_seconds": 30,
            "retry_count": 1,
            "output_fields": ["field1"]
        },
        {
            "id": "skill_2",
            "name": "Test Skill 2",
            "prompt_file": "prompts/skill_2.md",
            "parallel_group": 2,
            "timeout_seconds": 30,
            "retry_count": 1,
            "output_fields": ["field2"]
        }
    ],
    "post_processing": {
        "merge_strategy": "merge_deep",
        "validation_rules": []
    }
}
""")

        # Write prompt files
        (prompts_dir / "skill_1.md").write_text("# Skill 1\nExtract field1 from the document.")
        (prompts_dir / "skill_2.md").write_text("# Skill 2\nExtract field2 from the document.")

        # Write models.py
        (schema_dir / "models.py").write_text("""
from pydantic import BaseModel
from typing import Optional

class TestOutput(BaseModel):
    field1: Optional[str] = None
    field2: Optional[str] = None
""")

        yield skills_path


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns test data."""
    from app.models.execution import TokenUsage

    client = AsyncMock()
    client.extract_json = AsyncMock(
        return_value=(
            {"field1": "value1"},
            TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )
    )
    return client


@pytest.fixture
def app_client(temp_skills_dir: Path) -> Generator[TestClient, None, None]:
    """Create test client with initialized registry."""
    # Reset singleton before tests
    from app.services.skill_registry import SkillRegistry

    SkillRegistry.reset()

    # Update settings
    os.environ["LOCAL_SKILLS_PATH"] = str(temp_skills_dir)
    os.environ["SKILLS_BASE_PATH"] = ""

    # Clear settings cache
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as client:
        yield client

    # Cleanup
    SkillRegistry.reset()
    get_settings.cache_clear()
