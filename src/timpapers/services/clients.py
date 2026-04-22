"""External API clients for OpenAlex and Semantic Scholar."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx

from timpapers.config import get_settings
from timpapers.services.bibliography import BibliographyEntry, extract_bibliography_entries, to_raw_bibliography_url

logger = logging.getLogger(__name__)


async def _request_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    service: str,
    not_found_ok: bool = False,
    retries: int = 4,
) -> dict[str, Any] | None:
    """Perform a JSON request with retry/backoff for transient and rate-limit failures."""

    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            delay = min(30.0, 1.5 * (2**attempt))
            logger.warning("%s request failed; retrying in %.1fs error=%s", service, delay, exc)
            await asyncio.sleep(delay)
            continue

        if response.status_code == 404 and not_found_ok:
            return None

        if response.status_code in {429, 500, 502, 503, 504}:
            if attempt == retries:
                response.raise_for_status()
            delay = _retry_delay_seconds(response, attempt)
            logger.warning("%s returned %s; retrying in %.1fs", service, response.status_code, delay)
            await asyncio.sleep(delay)
            continue

        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    return None


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    """Choose a retry delay from Retry-After or exponential backoff."""

    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                return max(1.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                pass
    return min(60.0, 2.0 * (2**attempt))


class OpenAlexClient:
    """Thin OpenAlex API wrapper."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.openalex_base_url
        self.api_key = settings.openalex_api_key
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

        params = {"api_key": self.api_key} if self.api_key else None
        entity_id = quote(f"https://doi.org/{doi}", safe="")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await _request_json(
                client,
                f"{self.base_url}/works/{entity_id}",
                params=params,
                service="OpenAlex",
                not_found_ok=True,
            )

    async def fetch_works_by_doi(self, dois: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch OpenAlex works for a DOI collection."""

        unique_dois = list(dict.fromkeys(doi.lower() for doi in dois if doi))
        if not unique_dois:
            return {}

        semaphore = asyncio.Semaphore(2)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                params = {"api_key": self.api_key} if self.api_key else None
                entity_id = quote(f"https://doi.org/{doi}", safe="")
                async with semaphore:
                    try:
                        payload = await _request_json(
                            client,
                            f"{self.base_url}/works/{entity_id}",
                            params=params,
                            service="OpenAlex",
                            not_found_ok=True,
                        )
                    except httpx.HTTPError as exc:
                        logger.warning("OpenAlex fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None
                await asyncio.sleep(0.1)
                return doi, payload

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

        semaphore = asyncio.Semaphore(2 if self.mailto else 1)
        params = {"mailto": self.mailto} if self.mailto else {}

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                encoded = quote(doi, safe="")
                async with semaphore:
                    try:
                        payload = await _request_json(
                            client,
                            f"{self.base_url}/works/{encoded}",
                            params=params,
                            service="Crossref",
                            not_found_ok=True,
                        )
                    except httpx.HTTPError as exc:
                        logger.warning("Crossref fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None
                await asyncio.sleep(0.2 if self.mailto else 0.4)
                if payload is None:
                    return doi, None
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
        semaphore = asyncio.Semaphore(2 if self.api_key else 1)
        params = {"fields": "title,venue,year,authors,citationCount,externalIds,paperId"}

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            async def fetch_one(doi: str) -> tuple[str, dict[str, Any] | None]:
                paper_id = f"DOI:{doi}"
                async with semaphore:
                    try:
                        payload = await _request_json(
                            client,
                            f"{self.base_url}/paper/{quote(paper_id, safe='')}",
                            params=params,
                            service="Semantic Scholar",
                            not_found_ok=True,
                        )
                    except httpx.HTTPError as exc:
                        logger.warning("Semantic Scholar fetch failed for doi=%s error=%s", doi, exc)
                        return doi, None
                await asyncio.sleep(0.25)
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


class ScholarlyClient:
    """Best-effort Google Scholar scraping via the scholarly package."""

    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.scholarly_enabled
        self.proxy_mode = settings.scholarly_proxy_mode.strip().lower()
        self.proxy_http = settings.scholarly_proxy_http
        self.proxy_https = settings.scholarly_proxy_https
        self.tor_cmd = settings.scholarly_tor_cmd
        self.tor_sock_port = settings.scholarly_tor_sock_port
        self.tor_control_port = settings.scholarly_tor_control_port
        self.tor_password = settings.scholarly_tor_password

    async def fetch_works_by_doi(self, dois: Sequence[str]) -> dict[str, dict[str, Any] | None]:
        """Fetch publication snippets from Google Scholar for a DOI collection."""

        unique_dois = list(dict.fromkeys(doi.lower() for doi in dois if doi))
        if not unique_dois or not self.enabled:
            return {}

        try:
            from scholarly import ProxyGenerator, scholarly as scholar_api
        except ImportError:
            logger.info("scholarly is not installed; skipping Google Scholar enrichment")
            return {}

        self._configure_proxy(scholar_api, ProxyGenerator)

        results: dict[str, dict[str, Any] | None] = {}
        for doi in unique_dois:
            results[doi] = await asyncio.to_thread(self._fetch_one, scholar_api, doi)
        return results

    def _configure_proxy(self, scholar_api: Any, proxy_generator_cls: Any) -> None:
        """Configure scholarly proxying using documented ProxyGenerator modes."""

        if not self.enabled:
            scholar_api.use_proxy(None)
            return

        pg = proxy_generator_cls()
        mode = self.proxy_mode
        success: Any = False
        try:
            if mode == "tor_internal":
                success = pg.Tor_Internal(
                    tor_cmd=self.tor_cmd,
                    tor_sock_port=self.tor_sock_port,
                    tor_control_port=self.tor_control_port,
                )
            elif mode == "tor_external":
                if self.tor_sock_port and self.tor_control_port and self.tor_password:
                    success = pg.Tor_External(
                        tor_sock_port=self.tor_sock_port,
                        tor_control_port=self.tor_control_port,
                        tor_password=self.tor_password,
                    )
            elif mode == "single_proxy":
                success = pg.SingleProxy(http=self.proxy_http, https=self.proxy_https)
            elif mode == "free_proxies":
                success = pg.FreeProxies()
            else:
                scholar_api.use_proxy(None)
                return
        except Exception as exc:  # pragma: no cover - third-party proxy setup behavior
            logger.warning("scholarly proxy setup failed mode=%s error=%s", mode, exc)
            success = False

        proxy_works = success.get("proxy_works") if isinstance(success, dict) else bool(success)
        if proxy_works:
            scholar_api.use_proxy(pg)
        else:
            logger.warning("scholarly proxy mode=%s did not initialize; continuing without proxy", mode)
            scholar_api.use_proxy(None)

    def _fetch_one(self, scholar_api: Any, doi: str) -> dict[str, Any] | None:
        """Run one DOI query against Google Scholar."""

        try:
            publication = next(scholar_api.search_pubs(doi), None)
            if publication is None:
                return None
            try:
                filled = scholar_api.fill(publication)
            except Exception as exc:  # pragma: no cover - third-party scraper behavior
                logger.warning("scholarly fill failed for doi=%s error=%s", doi, exc)
                filled = publication
            return filled if isinstance(filled, dict) else None
        except Exception as exc:  # pragma: no cover - third-party scraper behavior
            logger.warning("scholarly search failed for doi=%s error=%s", doi, exc)
            return None
