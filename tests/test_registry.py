"""Tests for Skill Registry."""

import pytest
from pathlib import Path

from app.services.skill_registry import SkillRegistry, RegistryError
from app.models.events import EventType


class TestSkillRegistry:
    """Tests for SkillRegistry class."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry singleton before each test."""
        SkillRegistry.reset()
        yield
        SkillRegistry.reset()

    def test_singleton_pattern(self):
        """Test that registry is a singleton."""
        reg1 = SkillRegistry()
        reg2 = SkillRegistry()
        assert reg1 is reg2

    def test_initialize_with_local_path(self, temp_skills_dir: Path):
        """Test initializing registry with local skills path."""
        from unittest.mock import MagicMock, patch

        # Mock settings
        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            commit = registry.initialize()

            assert commit == "local"
            assert registry.schemas_count == 1
            assert registry.skills_count == 2

    def test_get_schema(self, temp_skills_dir: Path):
        """Test getting a schema by ID."""
        from unittest.mock import MagicMock, patch

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()

            schema = registry.get_schema("test_schema")
            assert schema is not None
            assert schema.config.schema_id == "test_schema"

            # Test non-existent schema
            assert registry.get_schema("nonexistent") is None

    def test_get_schema_or_raise(self, temp_skills_dir: Path):
        """Test get_schema_or_raise method."""
        from unittest.mock import MagicMock, patch

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()

            # Should succeed
            schema = registry.get_schema_or_raise("test_schema")
            assert schema is not None

            # Should raise
            with pytest.raises(RegistryError, match="not found"):
                registry.get_schema_or_raise("nonexistent")

    def test_list_skills(self, temp_skills_dir: Path):
        """Test listing skills."""
        from unittest.mock import MagicMock, patch

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()

            # List all skills
            all_skills = registry.list_skills()
            assert len(all_skills) == 2

            # List skills for specific schema
            schema_skills = registry.list_skills("test_schema")
            assert len(schema_skills) == 2

            # List skills for non-existent schema
            empty_skills = registry.list_skills("nonexistent")
            assert len(empty_skills) == 0

    def test_get_skill(self, temp_skills_dir: Path):
        """Test getting a specific skill."""
        from unittest.mock import MagicMock, patch

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()

            skill = registry.get_skill("test_schema", "skill_1")
            assert skill is not None
            assert skill.id == "skill_1"

            # Non-existent skill
            assert registry.get_skill("test_schema", "nonexistent") is None

    def test_events_emitted(self, temp_skills_dir: Path):
        """Test that events are emitted during operations."""
        from unittest.mock import MagicMock, patch

        settings = MagicMock()
        settings.github_repo_url = ""
        settings.local_skills_path = str(temp_skills_dir)
        settings.skills_base_path = ""

        with patch('app.services.skill_registry.get_settings', return_value=settings):
            registry = SkillRegistry(settings)
            registry.initialize()

            events = registry.get_recent_events()
            event_types = [e.type for e in events]

            # Should have schema created and registry reloaded events
            assert EventType.SCHEMA_CREATED in event_types
            assert EventType.REGISTRY_RELOADED in event_types

    def test_reload_not_initialized(self):
        """Test reload fails when not initialized."""
        registry = SkillRegistry()

        with pytest.raises(RegistryError, match="not initialized"):
            registry.reload()
