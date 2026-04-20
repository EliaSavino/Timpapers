"""Normalization helpers for external scholarly APIs."""

from __future__ import annotations


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
        "openalex_work_id": str(work.get("id") or ""),
        "citation_count": int(work.get("cited_by_count") or 0),
    }
