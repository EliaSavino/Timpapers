"""Normalization helpers for external scholarly APIs."""

from __future__ import annotations

from typing import Any

from timpapers.services.bibliography import BibliographyEntry, normalize_doi


def normalize_openalex_work(work: dict[str, object]) -> dict[str, object]:
    """Normalize OpenAlex work object into persistence-ready dictionary."""

    authorships = work.get("authorships", []) if isinstance(work, dict) else []
    author_names: list[str] = []
    for a in authorships:
        if isinstance(a, dict):
            author = a.get("author", {})
            if isinstance(author, dict) and author.get("display_name"):
                author_names.append(str(author["display_name"]))

    primary_location = work.get("primary_location", {}) if isinstance(work, dict) else {}
    source = primary_location.get("source", {}) if isinstance(primary_location, dict) else {}

    return {
        "title": str(work.get("display_name") or "Untitled"),
        "year": work.get("publication_year"),
        "doi": str(work.get("doi") or "").replace("https://doi.org/", "") or None,
        "venue": source.get("display_name") if isinstance(source, dict) else None,
        "author_list": ", ".join(author_names),
        "external_work_id": str(work.get("id") or ""),
        "citation_count": int(work.get("cited_by_count") or 0),
    }


def normalize_bibliography_entry(entry: BibliographyEntry) -> dict[str, object]:
    """Normalize one parsed bibliography entry into persistence-ready metadata."""

    return {
        "title": entry.title or "Untitled",
        "year": entry.year,
        "doi": entry.doi,
        "venue": entry.venue,
        "author_list": entry.author_list,
        "external_work_id": f"bib:{entry.key}",
        "citation_count": None,
    }


def normalize_crossref_work(work: dict[str, Any], entry: BibliographyEntry) -> dict[str, object]:
    """Normalize Crossref work metadata with BibTeX fallback values."""

    title_values = work.get("title", [])
    title = title_values[0] if isinstance(title_values, list) and title_values else entry.title

    venue_values = work.get("container-title", [])
    venue = venue_values[0] if isinstance(venue_values, list) and venue_values else entry.venue

    authors = work.get("author", [])
    author_list = entry.author_list
    if isinstance(authors, list) and authors:
        formatted = [_format_crossref_author(author) for author in authors if isinstance(author, dict)]
        cleaned = [name for name in formatted if name]
        if cleaned:
            author_list = ", ".join(cleaned)

    return {
        "title": str(title or "Untitled"),
        "year": _extract_crossref_year(work) or entry.year,
        "doi": normalize_doi(str(work.get("DOI") or entry.doi or "")) or entry.doi,
        "venue": str(venue) if venue else None,
        "author_list": author_list,
        "external_work_id": f"bib:{entry.key}",
        "citation_count": int(work.get("is-referenced-by-count") or 0),
    }


def normalize_openalex_doi_work(work: dict[str, Any], entry: BibliographyEntry) -> dict[str, object]:
    """Normalize an OpenAlex DOI lookup using bibliography fallback values."""

    normalized = normalize_openalex_work(work)
    return {
        "title": str(normalized["title"] or entry.title or "Untitled"),
        "year": normalized["year"] or entry.year,
        "doi": normalize_doi(str(normalized["doi"] or entry.doi or "")) or entry.doi,
        "venue": normalized["venue"] if normalized["venue"] else entry.venue,
        "author_list": str(normalized["author_list"] or entry.author_list),
        "external_work_id": f"bib:{entry.key}",
        "citation_count": int(normalized["citation_count"] or 0),
    }


def normalize_semanticscholar_work(work: dict[str, Any], entry: BibliographyEntry) -> dict[str, object]:
    """Normalize a Semantic Scholar DOI lookup using bibliography fallback values."""

    authors = work.get("authors", [])
    author_list = entry.author_list
    if isinstance(authors, list) and authors:
        cleaned = []
        for author in authors:
            if isinstance(author, dict) and author.get("name"):
                cleaned.append(str(author["name"]))
        if cleaned:
            author_list = ", ".join(cleaned)

    return {
        "title": str(work.get("title") or entry.title or "Untitled"),
        "year": work.get("year") or entry.year,
        "doi": normalize_doi(str(_semanticscholar_doi(work) or entry.doi or "")) or entry.doi,
        "venue": str(work.get("venue") or entry.venue) if work.get("venue") or entry.venue else None,
        "author_list": author_list,
        "external_work_id": f"bib:{entry.key}",
        "citation_count": int(work.get("citationCount") or 0),
    }


def normalize_scholarly_work(work: dict[str, Any], entry: BibliographyEntry) -> dict[str, object]:
    """Normalize a scholarly Google Scholar publication using bibliography fallback values."""

    bib = work.get("bib", {})
    if not isinstance(bib, dict):
        bib = {}

    author_list = entry.author_list
    raw_author = bib.get("author")
    if isinstance(raw_author, list) and raw_author:
        author_list = ", ".join(str(author) for author in raw_author if author)
    elif isinstance(raw_author, str) and raw_author.strip():
        author_list = raw_author

    venue = bib.get("venue") or bib.get("journal") or entry.venue
    title = bib.get("title") or work.get("title") or entry.title
    year = _scholarly_year(bib.get("pub_year") or bib.get("year")) or entry.year

    return {
        "title": str(title or "Untitled"),
        "year": year,
        "doi": entry.doi,
        "venue": str(venue) if venue else None,
        "author_list": author_list,
        "external_work_id": f"bib:{entry.key}",
        "citation_count": int(work.get("num_citations") or 0),
    }


def _format_crossref_author(author: dict[str, Any]) -> str:
    given = str(author.get("given") or "").strip()
    family = str(author.get("family") or "").strip()
    name = str(author.get("name") or "").strip()
    if given and family:
        return f"{given} {family}"
    return name or family or given


def _extract_crossref_year(work: dict[str, Any]) -> int | None:
    for field in ("published-print", "published-online", "issued", "created"):
        date_part = work.get(field, {})
        if not isinstance(date_part, dict):
            continue
        parts = date_part.get("date-parts", [])
        if not isinstance(parts, list) or not parts:
            continue
        first = parts[0]
        if isinstance(first, list) and first:
            try:
                return int(first[0])
            except (TypeError, ValueError):
                return None
    return None


def _semanticscholar_doi(work: dict[str, Any]) -> str | None:
    external_ids = work.get("externalIds", {})
    if not isinstance(external_ids, dict):
        return None
    doi = external_ids.get("DOI")
    return str(doi) if doi else None


def _scholarly_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
