"""Tests for Git loader service."""

from pathlib import Path

import pytest

from app.services.git_loader import GitLoader, GitLoaderError


class TestGitLoader:
    """Tests for GitLoader class."""

    def test_list_schemas(self, temp_skills_dir: Path):
        """Test listing available schemas."""
        # Create settings mock
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        loader = GitLoader(settings)
        loader.clone_or_pull()

        schemas = loader.list_schemas()
        assert "test_schema" in schemas

    def test_load_schema_config(self, temp_skills_dir: Path):
        """Test loading schema configuration."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        loader = GitLoader(settings)
        loader.clone_or_pull()

        config, schema_dir = loader.load_schema_config("test_schema")

        assert config.schema_id == "test_schema"
        assert config.version == "1.0.0"
        assert len(config.skills) == 2

    def test_load_skill_prompt(self, temp_skills_dir: Path):
        """Test loading skill prompt content."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        loader = GitLoader(settings)
        loader.clone_or_pull()

        _, schema_dir = loader.load_schema_config("test_schema")
        prompt = loader.load_skill_prompt(schema_dir, "prompts/skill_1.md")

        assert "Skill 1" in prompt
        assert "field1" in prompt

    def test_load_full_schema(self, temp_skills_dir: Path):
        """Test loading a full schema with all skills."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        loader = GitLoader(settings)
        loader.clone_or_pull()

        skills = loader.load_full_schema("test_schema")

        assert len(skills) == 2
        assert "skill_1" in skills
        assert "skill_2" in skills
        assert skills["skill_1"].prompt is not None

    def test_get_changed_schemas(self, temp_skills_dir: Path):
        """Test determining affected schemas from file changes."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = "skills"

        loader = GitLoader(settings)

        changed_files = [
            "skills/test_schema/prompts/skill_1.md",
            "skills/other_schema/schema.json",
            "unrelated/file.py",
        ]

        affected = loader.get_changed_schemas(changed_files)

        assert "test_schema" in affected
        assert "other_schema" in affected
        assert len(affected) == 2

    def test_schema_not_found(self, temp_skills_dir: Path):
        """Test error when schema not found."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        loader = GitLoader(settings)
        loader.clone_or_pull()

        with pytest.raises(GitLoaderError, match="Schema config not found"):
            loader.load_schema_config("nonexistent_schema")

    def test_no_config_error(self):
        """Test error when no Git URL or local path configured."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = ""

        loader = GitLoader(settings)

        with pytest.raises(GitLoaderError, match="No GitHub repo URL"):
            loader.clone_or_pull()
