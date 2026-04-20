"""External API clients for OpenAlex and Semantic Scholar."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import httpx

from timpapers.config import get_settings

logger = logging.getLogger(__name__)


class OpenAlexClient:
    """Thin OpenAlex API wrapper."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.openalex_base_url
        self.timeout = settings.request_timeout_seconds

    async def search_author(self, full_name: str) -> list[dict[str, Any]]:
        """Search author candidates by display name."""

        params = {"search": full_name, "per-page": 5}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/authors", params=params)
            response.raise_for_status()
            data = response.json()
        return data.get("results", [])

    async def fetch_author_works(self, openalex_author_id: str) -> list[dict[str, Any]]:
        """Fetch works for a specific OpenAlex author ID."""

        params = {"filter": f"authorships.author.id:{openalex_author_id}", "per-page": 200}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/works", params=params)
            response.raise_for_status()
            payload = response.json()
        return payload.get("results", [])


class SemanticScholarClient:
    """Thin Semantic Scholar API wrapper used as enrichment fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.semanticscholar_base_url
        self.timeout = settings.request_timeout_seconds
        self.api_key = settings.semanticscholar_api_key

    async def search_author(self, full_name: str) -> list[dict[str, Any]]:
        """Search Semantic Scholar author candidates."""

        headers = {"x-api-key": self.api_key} if self.api_key else {}
        params = {"query": full_name, "limit": 5, "fields": "name,paperCount,citationCount"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            response = await client.get(f"{self.base_url}/author/search", params=params)
            response.raise_for_status()
        return response.json().get("data", [])

    async def enrich_citations(self, paper_ids: Sequence[str]) -> dict[str, int]:
        """Fetch citation counts for known Semantic Scholar paper IDs."""

        if not paper_ids:
            return {}
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        fields = "paperId,citationCount"
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            tasks = [client.get(f"{self.base_url}/paper/{pid}", params={"fields": fields}) for pid in paper_ids]
            responses = await asyncio.gather(*tasks)
        enriched: dict[str, int] = {}
        for res in responses:
            if res.status_code == 200:
                obj = res.json()
                enriched[obj.get("paperId", "")] = int(obj.get("citationCount", 0))
            else:
                logger.warning("Semantic Scholar enrichment failed: status=%s", res.status_code)
        return enriched
