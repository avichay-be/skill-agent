"""GitHub/Git loader service for fetching skills from remote repositories."""

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from app.core.config import Settings, get_settings
from app.models.schema import SchemaConfig
from app.models.skill import Skill, SkillConfig

logger = logging.getLogger(__name__)


class GitLoaderError(Exception):
    """Error during Git operations."""

    pass


class GitLoader:
    """Loads skills from a Git repository."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._repo: Optional[Repo] = None
        self._local_path: Optional[Path] = None
        self._is_temp_dir = False

    @property
    def local_path(self) -> Optional[Path]:
        """Get local repository path."""
        return self._local_path

    @property
    def current_commit(self) -> Optional[str]:
        """Get current HEAD commit SHA."""
        if self._repo:
            return self._repo.head.commit.hexsha
        return None

    def _get_clone_url(self) -> str:
        """Build clone URL with authentication if token provided."""
        url = self.settings.github_repo_url

        if self.settings.github_token and "github.com" in url:
            # Insert token for HTTPS URLs
            if url.startswith("https://"):
                url = url.replace("https://", f"https://{self.settings.github_token}@")
        return url

    def clone_or_pull(self, target_path: Optional[str] = None) -> str:
        """Clone repository or pull latest changes.

        Args:
            target_path: Local path to clone to. If None, uses temp directory.

        Returns:
            Current commit SHA after operation.
        """
        # Use local skills path if configured and no remote URL
        if not self.settings.github_repo_url and self.settings.local_skills_path:
            self._local_path = Path(self.settings.local_skills_path)
            logger.info(f"Using local skills path: {self._local_path}")
            return "local"

        if not self.settings.github_repo_url:
            raise GitLoaderError("No GitHub repo URL or local skills path configured")

        if target_path:
            self._local_path = Path(target_path)
            self._is_temp_dir = False
        elif self._local_path is None:
            self._local_path = Path(tempfile.mkdtemp(prefix="skills-"))
            self._is_temp_dir = True

        try:
            if self._local_path.exists() and (self._local_path / ".git").exists():
                # Pull existing repo
                logger.info(f"Pulling latest from {self.settings.github_branch}")
                self._repo = Repo(self._local_path)
                origin = self._repo.remotes.origin
                origin.pull(self.settings.github_branch)
            else:
                # Clone fresh
                logger.info(f"Cloning {self.settings.github_repo_url}")
                self._local_path.mkdir(parents=True, exist_ok=True)
                self._repo = Repo.clone_from(
                    self._get_clone_url(),
                    self._local_path,
                    branch=self.settings.github_branch,
                )

            commit = self._repo.head.commit.hexsha
            logger.info(f"Repository at commit: {commit[:8]}")
            return commit

        except GitCommandError as e:
            raise GitLoaderError(f"Git operation failed: {e}") from e
        except InvalidGitRepositoryError as e:
            raise GitLoaderError(f"Invalid repository: {e}") from e

    def get_skills_base_path(self) -> Path:
        """Get the base path where skills are stored."""
        if not self._local_path:
            raise GitLoaderError("Repository not cloned. Call clone_or_pull() first.")

        # If skills_base_path is empty, use local_path directly
        if self.settings.skills_base_path:
            base = self._local_path / self.settings.skills_base_path
        else:
            base = self._local_path

        if not base.exists():
            raise GitLoaderError(f"Skills base path not found: {base}")
        return base

    def list_schemas(self) -> List[str]:
        """List all available schema IDs (directory names)."""
        base = self.get_skills_base_path()
        schemas = []

        for item in base.iterdir():
            if item.is_dir() and (item / "schema.json").exists():
                schemas.append(item.name)

        return sorted(schemas)

    def load_schema_config(self, schema_id: str) -> Tuple[SchemaConfig, Path]:
        """Load schema configuration from schema.json.

        Args:
            schema_id: The schema directory name.

        Returns:
            Tuple of (SchemaConfig, schema_directory_path)
        """
        base = self.get_skills_base_path()
        schema_dir = base / schema_id
        config_file = schema_dir / "schema.json"

        if not config_file.exists():
            raise GitLoaderError(f"Schema config not found: {config_file}")

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse skill configs
            skills_data = data.get("skills", [])
            skill_configs = [SkillConfig(**s) for s in skills_data]
            data["skills"] = skill_configs

            config = SchemaConfig(**data)
            return config, schema_dir

        except json.JSONDecodeError as e:
            raise GitLoaderError(f"Invalid JSON in {config_file}: {e}") from e
        except Exception as e:
            raise GitLoaderError(f"Failed to load schema config: {e}") from e

    def load_skill_prompt(self, schema_dir: Path, prompt_file: str) -> str:
        """Load skill prompt content from markdown file.

        Args:
            schema_dir: Path to schema directory.
            prompt_file: Relative path to prompt file from schema dir.

        Returns:
            Prompt content as string.
        """
        prompt_path = schema_dir / prompt_file

        if not prompt_path.exists():
            raise GitLoaderError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def load_full_schema(self, schema_id: str) -> Dict[str, Skill]:
        """Load a schema with all its skills fully populated.

        Args:
            schema_id: The schema to load.

        Returns:
            Dictionary of skill_id -> Skill with prompts loaded.
        """
        config, schema_dir = self.load_schema_config(schema_id)
        commit = self.current_commit or "unknown"
        skills: Dict[str, Skill] = {}

        for skill_config in config.skills:
            prompt = self.load_skill_prompt(schema_dir, skill_config.prompt_file)

            skill = Skill(
                id=skill_config.id,
                name=skill_config.name,
                prompt=prompt,
                config=skill_config,
                schema_id=schema_id,
                version=commit,
                file_path=str(schema_dir / skill_config.prompt_file),
            )
            skills[skill.id] = skill

        logger.info(f"Loaded {len(skills)} skills for schema '{schema_id}'")
        return skills

    def get_changed_schemas(self, changed_files: List[str]) -> List[str]:
        """Determine which schemas were affected by file changes.

        Args:
            changed_files: List of changed file paths from Git.

        Returns:
            List of affected schema IDs.
        """
        skills_prefix = self.settings.skills_base_path
        affected = set()

        for file_path in changed_files:
            if file_path.startswith(skills_prefix):
                # Extract schema_id from path like "skills/appraisal_report/prompts/x.md"
                parts = file_path[len(skills_prefix) :].strip("/").split("/")
                if parts:
                    affected.add(parts[0])

        return list(affected)

    def cleanup(self) -> None:
        """Clean up temporary directory if one was created."""
        if self._is_temp_dir and self._local_path and self._local_path.exists():
            logger.info(f"Cleaning up temp directory: {self._local_path}")
            shutil.rmtree(self._local_path)
            self._local_path = None
            self._repo = None

    def __enter__(self) -> "GitLoader":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.cleanup()
