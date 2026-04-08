"""Tests to verify Pydantic models use ConfigDict instead of deprecated class Config."""

import ast
from pathlib import Path
from typing import List, Tuple

import pytest

# Files that should use ConfigDict
MODEL_FILES = [
    "app/services/graph/state.py",
    "app/models/schema.py",
    "skills-library/valuation_report_analyzer/models.py",
]


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def find_deprecated_class_config(file_path: Path) -> List[Tuple[str, int]]:
    """Find all classes with deprecated class Config inner class.

    Returns a list of (class_name, line_number) tuples for classes with deprecated Config.
    """
    with open(file_path) as f:
        content = f.read()

    tree = ast.parse(content)
    deprecated_configs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this is a class that inherits from BaseModel or similar
            # and has a nested class named Config
            for body_item in node.body:
                if isinstance(body_item, ast.ClassDef) and body_item.name == "Config":
                    deprecated_configs.append((node.name, node.lineno))

    return deprecated_configs


def check_configdict_import(file_path: Path) -> bool:
    """Check if ConfigDict is imported from pydantic."""
    with open(file_path) as f:
        content = f.read()

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "pydantic":
                for alias in node.names:
                    if alias.name == "ConfigDict":
                        return True
    return False


def has_model_config_attribute(file_path: Path) -> bool:
    """Check if any class has model_config attribute (Pydantic v2 style)."""
    with open(file_path) as f:
        content = f.read()

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for body_item in node.body:
                if isinstance(body_item, ast.Assign):
                    for target in body_item.targets:
                        if isinstance(target, ast.Name) and target.id == "model_config":
                            return True
    return False


class TestPydanticConfigDictMigration:
    """Test that Pydantic models use ConfigDict instead of class Config."""

    @pytest.mark.parametrize("file_path", MODEL_FILES)
    def test_no_deprecated_class_config(self, file_path: str) -> None:
        """Verify no model uses deprecated class Config syntax."""
        project_root = get_project_root()
        full_path = project_root / file_path

        if not full_path.exists():
            pytest.skip(f"File {file_path} does not exist")

        deprecated = find_deprecated_class_config(full_path)

        assert len(deprecated) == 0, f"Found deprecated class Config in {file_path}: {deprecated}"

    @pytest.mark.parametrize("file_path", MODEL_FILES)
    def test_configdict_imported(self, file_path: str) -> None:
        """Verify ConfigDict is imported from pydantic for files with configs."""
        project_root = get_project_root()
        full_path = project_root / file_path

        if not full_path.exists():
            pytest.skip(f"File {file_path} does not exist")

        # Only check import if file has model_config attribute
        if has_model_config_attribute(full_path):
            has_import = check_configdict_import(full_path)
            assert has_import, f"ConfigDict not imported in {file_path}"

    @pytest.mark.parametrize("file_path", MODEL_FILES)
    def test_model_config_attribute_exists(self, file_path: str) -> None:
        """Verify models have model_config attribute (not class Config)."""
        project_root = get_project_root()
        full_path = project_root / file_path

        if not full_path.exists():
            pytest.skip(f"File {file_path} does not exist")

        # Check if file previously had class Config (by looking for populate_by_name or arbitrary_types_allowed)
        with open(full_path) as f:
            content = f.read()

        # Files that need ConfigDict should have model_config
        needs_config = "populate_by_name" in content or "arbitrary_types_allowed" in content

        if needs_config:
            has_model_config = has_model_config_attribute(full_path)
            assert has_model_config, f"model_config attribute not found in {file_path}"


class TestPydanticModelsBehavior:
    """Test that Pydantic models work correctly after migration."""

    def test_state_graph_arbitrary_types(self) -> None:
        """Test SkillGraphState allows arbitrary types."""
        from app.services.graph.state import SkillGraphState

        # Should not raise even with complex types
        state = SkillGraphState(
            document="test",
            schema_id="test_schema",
            execution_id="exec-123",
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )
        assert state.document == "test"
        assert state.execution_id == "exec-123"
