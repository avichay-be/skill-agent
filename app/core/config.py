"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

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
    environment: Literal["local", "test", "production"] = "local"

    # Authentication settings
    require_api_key: bool = False  # Set to True to enable API key authentication

    # API Keys for authentication (comma-separated string in env)
    api_keys_str: str = Field(default="dev-api-key", alias="api_keys")

    @computed_field  # type: ignore[misc]
    @property
    def api_keys(self) -> list[str]:
        """Parse comma-separated API keys."""
        return [k.strip() for k in self.api_keys_str.split(",") if k.strip()]

    # GitHub settings
    github_repo_url: str = ""
    github_token: str | None = None
    github_branch: str = "main"
    skills_base_path: str = ""  # Path within repo where skills live (empty = root)

    # Local skills path (for development or local-only mode)
    local_skills_path: str | None = None

    # Workflows path (separate from skills-library, defaults to ./workflows)
    workflows_path: str = "./workflows"

    # LLM settings
    default_vendor: str = "gemini"
    default_model: str | None = "gemini-3-flash-preview"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Google Gemini
    google_api_key: str | None = None
    gemini_model: str = "gemini-3-flash-preview"

    # Execution settings
    default_timeout_seconds: int = 60
    default_retry_count: int = 2
    max_parallel_skills: int = 10

    # Execution graph settings
    checkpoint_backend: Literal["memory", "sqlite"] = "sqlite"
    checkpoint_db_path: str = "./data/checkpoints.db"
    checkpoint_cleanup_days: int = 7

    enable_streaming: bool = True
    enable_human_review: bool = True
    enable_dynamic_selection: bool = False  # Experimental feature

    # Webhook settings
    webhook_secret: str | None = None  # For verifying incoming webhooks
    outbound_webhooks: list[str] = Field(default_factory=list)

    # CORS settings
    allowed_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        alias="allowed_origins",
    )

    @computed_field  # type: ignore[misc]
    @property
    def allowed_origins(self) -> list[str]:
        """Parse comma-separated allowed origins."""
        return [o.strip() for o in self.allowed_origins_str.split(",") if o.strip()]

    # File upload validation settings
    max_upload_size_mb: int = 10  # Max file upload size in MB
    allowed_file_extensions_str: str = Field(
        default=".txt,.md,.json,.csv,.xml,.html,.pdf",
        alias="allowed_file_extensions",
    )

    @computed_field  # type: ignore[misc]
    @property
    def allowed_file_extensions(self) -> list[str]:
        """Parse comma-separated allowed file extensions."""
        return [
            ext.strip().lower()
            for ext in self.allowed_file_extensions_str.split(",")
            if ext.strip()
        ]

    # Batch API settings
    enable_batch_api: bool = False  # Feature flag for Anthropic Batch API
    batch_poll_interval_seconds: int = 30  # Default polling interval

    # CosmosDB settings
    enable_cosmosdb: bool = False  # Feature flag for execution result storage
    cosmosdb_endpoint: str | None = None
    cosmosdb_key: str | None = None
    cosmosdb_database: str = "skill-agent"
    cosmosdb_container: str = "executions"

    # Request timeout settings
    request_timeout_seconds: int = 300  # 5 minutes default


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
