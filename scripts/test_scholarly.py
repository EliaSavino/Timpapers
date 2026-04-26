"""Probe Google Scholar via scholarly without running the Streamlit app.

Examples:
    python scripts/test_scholarly.py --author "Timothy Noel" --fill-author
    python scripts/test_scholarly.py --title "A fully automated flow-based approach"
    python scripts/test_scholarly.py --from-bib --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logger = logging.getLogger(__name__)


def main() -> int:
    """Run a targeted scholarly probe."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author", help="Search Google Scholar author profiles by name.")
    parser.add_argument("--author-id", help="Fill one Google Scholar author profile by Scholar ID.")
    parser.add_argument("--fill-author", action="store_true", help="Fill author profiles before printing.")
    parser.add_argument("--title", action="append", default=[], help="Search one paper title. Can repeat.")
    parser.add_argument(
        "--from-bib",
        action="store_true",
        help="Search titles from the configured bibliography URL.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum authors or bibliography titles.")
    parser.add_argument("--per-title", type=int, default=1, help="Maximum publication hits per title.")
    parser.add_argument(
        "--proxy-mode",
        choices=["config", "none", "free_proxies", "single_proxy", "tor_internal", "tor_external"],
        default="config",
        help="Proxy mode for this probe. Default uses author_config secret settings.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose logs.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        from scholarly import ProxyGenerator, scholarly as scholar_api
    except ImportError:
        print("scholarly is not installed. Install project dependencies first.", file=sys.stderr)
        return 2

    configure_proxy(scholar_api, ProxyGenerator, args.proxy_mode)

    output: dict[str, Any] = {
        "proxy_mode": effective_proxy_mode(args.proxy_mode),
        "authors": [],
        "author_profile": None,
        "title_results": [],
    }

    if args.author:
        output["authors"] = search_authors(
            scholar_api,
            args.author,
            limit=args.limit,
            fill=args.fill_author,
        )

    if args.author_id:
        output["author_profile"] = fill_author_id(scholar_api, args.author_id)

    titles = list(args.title)
    if args.from_bib:
        titles.extend(entry.title for entry in load_bibliography_entries(args.limit) if entry.title)

    for title in titles:
        output["title_results"].append(search_title(scholar_api, title, limit=args.per_title))

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print_report(output)

    if not any((output["authors"], output["author_profile"], output["title_results"])):
        print("No searches requested. Use --author, --author-id, --title, or --from-bib.", file=sys.stderr)
        return 1
    return 0


def configure_proxy(scholar_api: Any, proxy_generator_cls: Any, proxy_mode: str) -> None:
    """Configure scholarly proxying, without requiring app-level scholarly_enabled."""

    from timpapers.services.clients import ScholarlyClient

    if proxy_mode == "none":
        logger.info("scholarly proxy disabled for this probe")
        return

    client = ScholarlyClient()
    client.enabled = True
    if proxy_mode != "config":
        client.proxy_mode = proxy_mode
    logger.info("scholarly proxy mode=%s", client.proxy_mode)
    client._configure_proxy(scholar_api, proxy_generator_cls)


def effective_proxy_mode(proxy_mode: str) -> str:
    """Return the configured proxy mode without exposing proxy credentials."""

    from timpapers.config import get_settings

    if proxy_mode != "config":
        return proxy_mode
    return get_settings().scholarly_proxy_mode


def search_authors(scholar_api: Any, name: str, *, limit: int, fill: bool) -> list[dict[str, Any]]:
    """Search Scholar author profiles."""

    results = []
    for index, author in enumerate(scholar_api.search_author(name)):
        if index >= limit:
            break
        if fill:
            try:
                author = scholar_api.fill(author)
            except Exception as exc:
                logger.warning("author fill failed name=%s error=%s", name, exc)
        results.append(author_summary(author))
    return results


def fill_author_id(scholar_api: Any, author_id: str) -> dict[str, Any] | None:
    """Fetch one Scholar author profile by ID."""

    try:
        author = scholar_api.search_author_id(author_id)
        return author_summary(scholar_api.fill(author))
    except Exception as exc:
        logger.warning("author-id search failed id=%s error=%s", author_id, exc)
        return None


def search_title(scholar_api: Any, title: str, *, limit: int) -> dict[str, Any]:
    """Search Scholar publications by title."""

    matches = []
    try:
        for index, publication in enumerate(scholar_api.search_pubs(title)):
            if index >= limit:
                break
            try:
                publication = scholar_api.fill(publication)
            except Exception as exc:
                logger.warning("publication fill failed title=%s error=%s", title, exc)
            matches.append(publication_summary(publication))
    except Exception as exc:
        logger.warning("title search failed title=%s error=%s", title, exc)
    return {"query": title, "matches": matches}


def load_bibliography_entries(limit: int) -> list[Any]:
    """Load a few configured bibliography entries for title-based probes."""

    from timpapers.config import get_settings
    from timpapers.services.clients import BibliographyClient

    settings = get_settings()
    if not settings.author_bibliography_url:
        raise SystemExit("No author.bibliography_url is configured in the secret config.")
    entries = asyncio.run(BibliographyClient().fetch_entries(settings.author_bibliography_url))
    return entries[:limit]


def author_summary(author: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, printable author profile."""

    publications = author.get("publications", [])
    if not isinstance(publications, list):
        publications = []
    return {
        "name": author.get("name"),
        "scholar_id": author.get("scholar_id"),
        "affiliation": author.get("affiliation"),
        "citedby": author.get("citedby"),
        "hindex": author.get("hindex"),
        "i10index": author.get("i10index"),
        "interests": author.get("interests", []),
        "publication_count": len(publications),
        "sample_publications": [
            publication_summary(publication)
            for publication in publications[:5]
            if isinstance(publication, dict)
        ],
    }


def publication_summary(publication: dict[str, Any]) -> dict[str, Any]:
    """Return compact publication fields that are useful for debugging matching."""

    bib = publication.get("bib", {})
    if not isinstance(bib, dict):
        bib = {}
    return {
        "title": bib.get("title") or publication.get("title"),
        "year": bib.get("pub_year") or bib.get("year"),
        "venue": bib.get("venue") or bib.get("journal"),
        "authors": bib.get("author"),
        "num_citations": publication.get("num_citations"),
        "pub_url": publication.get("pub_url"),
        "author_pub_id": publication.get("author_pub_id"),
    }


def print_report(output: dict[str, Any]) -> None:
    """Print human-readable probe results."""

    print(f"Proxy mode: {output['proxy_mode']}")
    if output["authors"]:
        print("\nAuthor search results")
        for author in output["authors"]:
            print(
                "- "
                f"{author.get('name')} | id={author.get('scholar_id')} | "
                f"h={author.get('hindex')} | citedby={author.get('citedby')} | "
                f"pubs={author.get('publication_count')}"
            )

    if output["author_profile"]:
        author = output["author_profile"]
        print("\nAuthor profile")
        print(
            f"{author.get('name')} | id={author.get('scholar_id')} | "
            f"h={author.get('hindex')} | i10={author.get('i10index')} | "
            f"citedby={author.get('citedby')}"
        )
        for publication in author.get("sample_publications", []):
            print(f"- {publication.get('title')} | cites={publication.get('num_citations')}")

    if output["title_results"]:
        print("\nTitle search results")
        for result in output["title_results"]:
            print(f"Query: {result['query']}")
            if not result["matches"]:
                print("- no matches")
            for match in result["matches"]:
                print(
                    "- "
                    f"{match.get('title')} | year={match.get('year')} | "
                    f"cites={match.get('num_citations')} | venue={match.get('venue')}"
                )


if __name__ == "__main__":
    raise SystemExit(main())
