"""External API clients for OpenAlex and Semantic Scholar."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx

from timpapers.config import get_settings
from timpapers.services.bibliography import BibliographyEntry, extract_bibliography_entries, to_raw_bibliography_url

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

        params = {
            "filter": f"authorships.author.id:{openalex_author_id}",
            "per-page": 200,
            "cursor": "*",
        }
        works: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                response = await client.get(f"{self.base_url}/works", params=params)
                response.raise_for_status()
                payload = response.json()
                page_results = payload.get("results", [])
                if not isinstance(page_results, list):
                    break
                works.extend(page_results)

                meta = payload.get("meta", {})
                next_cursor = meta.get("next_cursor") if isinstance(meta, dict) else None
                if not next_cursor:
                    break
                params["cursor"] = str(next_cursor)
        return works

    async def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        """Fetch one OpenAlex work by DOI."""

        params = {"filter": f"doi:{doi}", "per-page": 1}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/works", params=params)
            response.raise_for_status()
            payload = response.json()
        results = payload.get("results", [])
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        return first if isinstance(first, dict) else None

    async def fetch_works_by_doi(self, dois: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch OpenAlex works for a DOI collection."""

        unique_dois = list(dict.fromkeys(doi.lower() for doi in dois if doi))
        if not unique_dois:
            return {}

        semaphore = asyncio.Semaphore(8)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                params = {"filter": f"doi:{doi}", "per-page": 1}
                async with semaphore:
                    try:
                        response = await client.get(f"{self.base_url}/works", params=params)
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.warning("OpenAlex fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None

                payload = response.json()
                results = payload.get("results", [])
                if not isinstance(results, list) or not results:
                    return doi, None
                first = results[0]
                return doi, first if isinstance(first, dict) else None

            results = await asyncio.gather(*(fetch_one(doi) for doi in unique_dois))
        return dict(results)


class BibliographyClient:
    """Fetch and parse the configured public bibliography file."""

    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.request_timeout_seconds

    async def fetch_entries(self, bibliography_url: str) -> list[BibliographyEntry]:
        """Download and parse a public BibTeX file."""

        raw_url = to_raw_bibliography_url(bibliography_url)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(raw_url)
            response.raise_for_status()
        return extract_bibliography_entries(response.text)


class CrossrefClient:
    """Thin Crossref API wrapper for DOI metadata and citation counts."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.crossref_base_url
        self.timeout = settings.request_timeout_seconds
        self.mailto = settings.crossref_mailto
        user_agent = "TimPapers/0.2.0"
        if self.mailto:
            user_agent = f"{user_agent} (mailto:{self.mailto})"
        self.headers = {"User-Agent": user_agent}

    async def fetch_work(self, doi: str) -> dict[str, Any] | None:
        """Fetch one Crossref work by DOI."""

        params = {"mailto": self.mailto} if self.mailto else {}
        encoded = quote(doi, safe="")
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/works/{encoded}", params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
        payload = response.json()
        message = payload.get("message", {})
        return message if isinstance(message, dict) else None

    async def fetch_works(self, dois: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch Crossref works for a DOI collection with bounded concurrency."""

        unique_dois = list(dict.fromkeys(doi.lower() for doi in dois if doi))
        if not unique_dois:
            return {}

        semaphore = asyncio.Semaphore(8)
        params = {"mailto": self.mailto} if self.mailto else {}

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                encoded = quote(doi, safe="")
                async with semaphore:
                    try:
                        response = await client.get(f"{self.base_url}/works/{encoded}", params=params)
                        if response.status_code == 404:
                            return doi, None
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.warning("Crossref fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None

                payload = response.json()
                message = payload.get("message", {})
                return doi, message if isinstance(message, dict) else None

            results = await asyncio.gather(*(fetch_one(doi) for doi in unique_dois))
        return dict(results)


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

    async def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        """Fetch one Semantic Scholar paper by DOI."""

        headers = {"x-api-key": self.api_key} if self.api_key else {}
        params = {"fields": "title,venue,year,authors,citationCount,externalIds,paperId"}
        paper_id = f"DOI:{doi}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            response = await client.get(f"{self.base_url}/paper/{quote(paper_id, safe='')}", params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    async def fetch_works_by_doi(self, dois: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch Semantic Scholar papers for a DOI collection."""

        unique_dois = list(dict.fromkeys(doi.lower() for doi in dois if doi))
        if not unique_dois:
            return {}

        headers = {"x-api-key": self.api_key} if self.api_key else {}
        semaphore = asyncio.Semaphore(4 if self.api_key else 2)
        params = {"fields": "title,venue,year,authors,citationCount,externalIds,paperId"}

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                paper_id = f"DOI:{doi}"
                async with semaphore:
                    try:
                        response = await client.get(
                            f"{self.base_url}/paper/{quote(paper_id, safe='')}",
                            params=params,
                        )
                        if response.status_code == 404:
                            return doi, None
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.warning("Semantic Scholar fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None

                payload = response.json()
                return doi, payload if isinstance(payload, dict) else None

            results = await asyncio.gather(*(fetch_one(doi) for doi in unique_dois))
        return dict(results)

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
