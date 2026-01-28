"""Skill Registry - In-memory storage with dynamic model loading."""

import importlib.util
import logging
import sys
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Type

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.models.events import EventType, SkillEvent
from app.models.schema import LoadedSchema, SchemaConfig
from app.models.skill import Skill, SkillStatus
from app.services.git_loader import GitLoader

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Error in skill registry operations."""

    pass


class SkillRegistry:
    """In-memory registry for loaded schemas and skills."""

    _instance: Optional["SkillRegistry"] = None
    _lock = Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "SkillRegistry":
        """Singleton pattern for registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized: bool = False
        return cls._instance

    def __init__(self, settings: Optional[Settings] = None):
        if self._initialized:
            return

        self.settings = settings or get_settings()
        self._schemas: Dict[str, LoadedSchema] = {}
        self._git_loader: Optional[GitLoader] = None
        self._current_commit: Optional[str] = None
        self._events: List[SkillEvent] = []
        self._initialized = True

        logger.info("SkillRegistry initialized")

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance._schemas.clear()
                cls._instance._events.clear()
                cls._instance._git_loader = None
                cls._instance._current_commit = None
            cls._instance = None

    def _emit_event(
        self,
        event_type: EventType,
        schema_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> SkillEvent:
        """Emit and store an event."""
        event = SkillEvent(
            type=event_type,
            schema_id=schema_id,
            skill_id=skill_id,
            git_commit=self._current_commit,
            payload=payload or {},
        )
        self._events.append(event)
        logger.debug(f"Event emitted: {event.type} for schema={schema_id}, skill={skill_id}")
        return event

    def get_recent_events(self, limit: int = 50) -> List[SkillEvent]:
        """Get recent events."""
        return self._events[-limit:]

    def initialize(self, repo_path: Optional[str] = None) -> str:
        """Initialize registry by loading skills from Git or local path.

        Args:
            repo_path: Optional local path to clone repo to.

        Returns:
            Current git commit SHA.
        """
        logger.info("Initializing skill registry...")

        self._git_loader = GitLoader(self.settings)
        self._current_commit = self._git_loader.clone_or_pull(repo_path)

        # Load all schemas
        schema_ids = self._git_loader.list_schemas()
        logger.info(f"Found {len(schema_ids)} schemas: {schema_ids}")

        for schema_id in schema_ids:
            try:
                self._load_schema(schema_id)
            except Exception as e:
                logger.error(f"Failed to load schema '{schema_id}': {e}")

        self._emit_event(
            EventType.REGISTRY_RELOADED,
            payload={"schemas_loaded": len(self._schemas)},
        )

        return self._current_commit

    def _load_schema(self, schema_id: str) -> LoadedSchema:
        """Load a single schema with all skills."""
        if not self._git_loader:
            raise RegistryError("Registry not initialized. Call initialize() first.")

        # Load config and skills
        config, schema_dir = self._git_loader.load_schema_config(schema_id)
        skills = self._git_loader.load_full_schema(schema_id)

        # Try to load output model if specified
        output_model = None
        if config.output_model:
            output_model = self._load_output_model(schema_dir, config.output_model)

        loaded_schema = LoadedSchema(
            config=config,
            skills=skills,
            output_model=output_model,
            git_commit=self._current_commit or "unknown",
            source_path=str(schema_dir),
        )

        # Check if updating existing or creating new
        is_update = schema_id in self._schemas
        self._schemas[schema_id] = loaded_schema

        event_type = EventType.SCHEMA_UPDATED if is_update else EventType.SCHEMA_CREATED
        self._emit_event(event_type, schema_id=schema_id)

        logger.info(f"Loaded schema '{schema_id}' v{config.version} with {len(skills)} skills")
        return loaded_schema

    def _load_output_model(self, schema_dir: Path, model_path: str) -> Optional[Type[BaseModel]]:
        """Dynamically load a Pydantic model from the skills directory.

        Args:
            schema_dir: Path to schema directory.
            model_path: Python import path like "models.AppraisalReport".

        Returns:
            The loaded Pydantic model class, or None if loading fails.
        """
        try:
            # model_path format: "models.ClassName" or just "ClassName"
            if "." in model_path:
                module_name, class_name = model_path.rsplit(".", 1)
            else:
                module_name = "models"
                class_name = model_path

            # Build file path
            module_file = schema_dir / f"{module_name.replace('.', '/')}.py"

            if not module_file.exists():
                logger.warning(f"Model file not found: {module_file}")
                return None

            # Dynamic import
            spec = importlib.util.spec_from_file_location(
                f"skills.{schema_dir.name}.{module_name}",
                module_file,
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            model_class = getattr(module, class_name, None)

            if model_class and issubclass(model_class, BaseModel):
                logger.info(f"Loaded output model: {class_name}")
                return model_class  # type: ignore[no-any-return]
            else:
                logger.warning(f"Class '{class_name}' not found or not a BaseModel")
                return None

        except Exception as e:
            logger.error(f"Failed to load output model '{model_path}': {e}")
            return None

    def reload(self) -> str:
        """Reload all skills from Git (pull latest).

        Returns:
            New git commit SHA.
        """
        if not self._git_loader:
            raise RegistryError("Registry not initialized. Call initialize() first.")

        old_commit = self._current_commit
        self._current_commit = self._git_loader.clone_or_pull()

        if self._current_commit != old_commit:
            old_hash = old_commit[:8] if old_commit else "none"
            new_hash = self._current_commit[:8] if self._current_commit else "none"
            logger.info(f"New commit detected: {old_hash} -> {new_hash}")

            # Reload all schemas
            schema_ids = self._git_loader.list_schemas()
            for schema_id in schema_ids:
                try:
                    self._load_schema(schema_id)
                except Exception as e:
                    logger.error(f"Failed to reload schema '{schema_id}': {e}")

            self._emit_event(
                EventType.GIT_SYNC_COMPLETED,
                payload={"old_commit": old_commit, "new_commit": self._current_commit},
            )
        else:
            logger.info("No new commits, registry unchanged")

        return self._current_commit

    def reload_schema(self, schema_id: str) -> LoadedSchema:
        """Reload a specific schema.

        Args:
            schema_id: Schema to reload.

        Returns:
            Reloaded schema.
        """
        if not self._git_loader:
            raise RegistryError("Registry not initialized.")

        self._git_loader.clone_or_pull()  # Ensure latest
        return self._load_schema(schema_id)

    def reload_affected_schemas(self, changed_files: List[str]) -> List[str]:
        """Reload only schemas affected by file changes.

        Args:
            changed_files: List of changed file paths.

        Returns:
            List of reloaded schema IDs.
        """
        if not self._git_loader:
            raise RegistryError("Registry not initialized.")

        affected = self._git_loader.get_changed_schemas(changed_files)
        logger.info(f"Affected schemas from file changes: {affected}")

        # Pull latest first
        self._current_commit = self._git_loader.clone_or_pull()

        for schema_id in affected:
            try:
                self._load_schema(schema_id)
            except Exception as e:
                logger.error(f"Failed to reload schema '{schema_id}': {e}")

        return affected

    # Query methods

    def get_schema(self, schema_id: str) -> Optional[LoadedSchema]:
        """Get a loaded schema by ID."""
        return self._schemas.get(schema_id)

    def get_schema_or_raise(self, schema_id: str) -> LoadedSchema:
        """Get schema or raise error if not found."""
        schema = self._schemas.get(schema_id)
        if not schema:
            raise RegistryError(f"Schema '{schema_id}' not found")
        return schema

    def list_schemas(self) -> List[SchemaConfig]:
        """List all loaded schema configs."""
        return [s.config for s in self._schemas.values()]

    def get_skill(self, schema_id: str, skill_id: str) -> Optional[Skill]:
        """Get a specific skill."""
        schema = self._schemas.get(schema_id)
        if schema:
            return schema.skills.get(skill_id)
        return None

    def list_skills(self, schema_id: Optional[str] = None) -> List[Skill]:
        """List skills, optionally filtered by schema."""
        skills: List[Skill] = []

        if schema_id:
            schema = self._schemas.get(schema_id)
            if schema:
                skills.extend(schema.skills.values())
        else:
            for schema in self._schemas.values():
                skills.extend(schema.skills.values())

        return skills

    def get_active_skills(self, schema_id: str) -> List[Skill]:
        """Get only active skills for a schema."""
        schema = self._schemas.get(schema_id)
        if not schema:
            return []
        return [s for s in schema.skills.values() if s.config.status == SkillStatus.ACTIVE]

    @property
    def current_commit(self) -> Optional[str]:
        """Get current git commit."""
        return self._current_commit

    @property
    def schemas_count(self) -> int:
        """Get number of loaded schemas."""
        return len(self._schemas)

    @property
    def skills_count(self) -> int:
        """Get total number of loaded skills."""
        return sum(len(s.skills) for s in self._schemas.values())


# Convenience function for dependency injection
def get_registry() -> SkillRegistry:
    """Get the singleton registry instance."""
    return SkillRegistry()
