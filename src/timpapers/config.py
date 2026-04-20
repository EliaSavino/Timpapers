"""Application configuration for the Streamlit app."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="TP_", extra="ignore")

    app_name: str = "TimPapers"
    database_url: str = Field(default="sqlite:///./timpapers.db")
    author_name: str = ""
    author_bibliography_url: str = ""
    openalex_base_url: str = "https://api.openalex.org"
    crossref_base_url: str = "https://api.crossref.org"
    crossref_mailto: str | None = None
    semanticscholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    semanticscholar_api_key: str | None = None
    request_timeout_seconds: float = 20.0


def _load_file_settings() -> dict[str, str]:
    """Load optional repository-local author config."""

    config_path = Path("author_config.toml")
    if not config_path.exists():
        return {}

    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)

    author_cfg = payload.get("author", {})
    app_cfg = payload.get("app", {})
    values: dict[str, str] = {}
    if isinstance(author_cfg, dict):
        name = author_cfg.get("name")
        bibliography_url = author_cfg.get("bibliography_url")
        if isinstance(name, str):
            values["author_name"] = name
        if isinstance(bibliography_url, str):
            values["author_bibliography_url"] = bibliography_url
    if isinstance(app_cfg, dict):
        crossref_mailto = app_cfg.get("crossref_mailto")
        if isinstance(crossref_mailto, str):
            values["crossref_mailto"] = crossref_mailto
    return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton settings instance."""

    settings = Settings()
    file_settings = _load_file_settings()
    if not file_settings:
        return settings

    updates = {
        key: value
        for key, value in file_settings.items()
        if getattr(settings, key) in ("", None)
    }
    if not updates:
        return settings
    return settings.model_copy(update=updates)
