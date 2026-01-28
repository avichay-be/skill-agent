"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App settings
    app_name: str = "Skill Agent"
    debug: bool = False

    # Authentication settings
    require_api_key: bool = False  # Set to True to enable API key authentication

    # API Keys for authentication (comma-separated string in env)
    api_keys_str: str = Field(default="dev-api-key", alias="api_keys")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def api_keys(self) -> List[str]:
        """Parse comma-separated API keys."""
        return [k.strip() for k in self.api_keys_str.split(",") if k.strip()]

    # GitHub settings
    github_repo_url: str = ""
    github_token: Optional[str] = None
    github_branch: str = "main"
    skills_base_path: str = ""  # Path within repo where skills live (empty = root)

    # Local skills path (for development or local-only mode)
    local_skills_path: Optional[str] = None

    # LLM settings
    default_vendor: str = "gemini"
    default_model: Optional[str] = "gemini-3-flash-preview"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # Google Gemini
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-3-flash-preview"

    # Execution settings
    default_timeout_seconds: int = 60
    default_retry_count: int = 2
    max_parallel_skills: int = 10

    # LangGraph settings
    use_langgraph: bool = True  # Feature flag to enable/disable LangGraph
    checkpoint_backend: Literal["memory", "sqlite"] = "sqlite"
    checkpoint_db_path: str = "./data/checkpoints.db"
    checkpoint_cleanup_days: int = 7

    enable_streaming: bool = True
    enable_human_review: bool = True
    enable_dynamic_selection: bool = False  # Experimental feature

    # Webhook settings
    webhook_secret: Optional[str] = None  # For verifying incoming webhooks
    outbound_webhooks: List[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
