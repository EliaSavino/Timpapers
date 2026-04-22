"""Application configuration for the Streamlit app."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
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
    openalex_api_key: str | None = None
    crossref_base_url: str = "https://api.crossref.org"
    crossref_mailto: str | None = None
    scholarly_enabled: bool = False
    scholarly_proxy_mode: str = "free_proxies"
    scholarly_proxy_http: str | None = None
    scholarly_proxy_https: str | None = None
    scholarly_tor_cmd: str | None = None
    scholarly_tor_sock_port: int | None = None
    scholarly_tor_control_port: int | None = None
    scholarly_tor_password: str | None = None
    semanticscholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    semanticscholar_api_key: str | None = None
    request_timeout_seconds: float = 20.0


def _load_file_settings() -> dict[str, Any]:
    """Load optional secret config from local files."""

    candidate_paths = (
        Path("author_config.secret.toml"),
        Path(".streamlit/secrets.toml"),
    )
    payload: dict[str, Any] | None = None
    for config_path in candidate_paths:
        if not config_path.exists():
            continue
        with config_path.open("rb") as handle:
            payload = tomllib.load(handle)
        break

    if payload is None:
        return {}

    author_cfg = payload.get("author", {})
    app_cfg = payload.get("app", {})
    values: dict[str, Any] = {}
    if isinstance(author_cfg, dict):
        name = author_cfg.get("name")
        bibliography_url = author_cfg.get("bibliography_url")
        if isinstance(name, str):
            values["author_name"] = name
        if isinstance(bibliography_url, str):
            values["author_bibliography_url"] = bibliography_url
    if isinstance(app_cfg, dict):
        openalex_api_key = app_cfg.get("openalex_api_key")
        crossref_mailto = app_cfg.get("crossref_mailto")
        scholarly_enabled = app_cfg.get("scholarly_enabled")
        scholarly_proxy_mode = app_cfg.get("scholarly_proxy_mode")
        scholarly_proxy_http = app_cfg.get("scholarly_proxy_http")
        scholarly_proxy_https = app_cfg.get("scholarly_proxy_https")
        scholarly_tor_cmd = app_cfg.get("scholarly_tor_cmd")
        scholarly_tor_sock_port = app_cfg.get("scholarly_tor_sock_port")
        scholarly_tor_control_port = app_cfg.get("scholarly_tor_control_port")
        scholarly_tor_password = app_cfg.get("scholarly_tor_password")
        if isinstance(openalex_api_key, str):
            values["openalex_api_key"] = openalex_api_key
        if isinstance(crossref_mailto, str):
            values["crossref_mailto"] = crossref_mailto
        if isinstance(scholarly_enabled, bool):
            values["scholarly_enabled"] = scholarly_enabled
        if isinstance(scholarly_proxy_mode, str):
            values["scholarly_proxy_mode"] = scholarly_proxy_mode
        if isinstance(scholarly_proxy_http, str):
            values["scholarly_proxy_http"] = scholarly_proxy_http
        if isinstance(scholarly_proxy_https, str):
            values["scholarly_proxy_https"] = scholarly_proxy_https
        if isinstance(scholarly_tor_cmd, str):
            values["scholarly_tor_cmd"] = scholarly_tor_cmd
        if isinstance(scholarly_tor_sock_port, int):
            values["scholarly_tor_sock_port"] = scholarly_tor_sock_port
        if isinstance(scholarly_tor_control_port, int):
            values["scholarly_tor_control_port"] = scholarly_tor_control_port
        if isinstance(scholarly_tor_password, str):
            values["scholarly_tor_password"] = scholarly_tor_password
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
