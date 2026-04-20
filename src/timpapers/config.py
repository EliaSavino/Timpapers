"""Application configuration for the Streamlit app."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="TP_", extra="ignore")

    app_name: str = "TimPapers"
    database_url: str = Field(default="sqlite:///./timpapers.db")
    openalex_base_url: str = "https://api.openalex.org"
    semanticscholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    semanticscholar_api_key: str | None = None
    request_timeout_seconds: float = 20.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton settings instance."""

    return Settings()
