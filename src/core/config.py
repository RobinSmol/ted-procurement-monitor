from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-wide configuration loaded from environment variables.

    Uses pydantic-settings to automatically read values from a .env file,
    with strong typing and validation on every field. Acts as the single
    injection point for all external configuration — no other module
    should read from os.environ directly.

    Field descriptions are defined inline via Field() and serve as
    the authoritative configuration documentation.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    ted_db_path: Path = Field(
        default=Path("data/ted_database.db"),
        description="The relative path for the sqlite database.",
    )
    chroma_db_path: Path = Field(
        default=Path("data/chroma_database"),
        description="The relative path for the chroma db",
    )
    ted_api_page_limit: int = 200
    ted_api_timeout: int = 10
    embedding_model_name: str = "paraphrase-multilingual-mpnet-base-v2"
    semantic_weight: float = Field(default=0.7, le=1.0, ge=0.0)
    recency_weight: float = Field(default=0.3, le=1.0, ge=0.0)
    recency_decay_days: int = 30
    smtp_host: str = Field(default="smtp-relay.brevo.com")
    smtp_port: int = Field(default=587)
    smtp_login: str = Field(default="")
    smtp_password: str = Field(default="")
    sender_email: str = Field(default="")
    dashboard_url: str = Field(default="http://localhost:8501")

    @model_validator(mode="after")
    def validate_sum_recency_semantic(self):
        """Validates that semantic and recency weights sum to exactly 1.0.

        Enforces the constraint that the scoring formula remains a proper
        weighted average. Raises at startup rather than producing silently
        incorrect search scores at runtime.

        Returns:
            The validated AppSettings instance.

        Raises:
            ValueError: If semantic_weight + recency_weight != 1.0.
        """
        total = self.recency_weight + self.semantic_weight
        if round(total, 10) != 1.0:
            raise ValueError("recency and semantic weight must sum to 1.0")
        return self


settings = AppSettings()  # type: ignore[call-arg]
