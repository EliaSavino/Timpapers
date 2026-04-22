"""Idempotent ingestion and synchronization service."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from timpapers.config import get_settings
from sqlalchemy import select
from sqlalchemy.orm import Session

from timpapers.models import (
    Author,
    CitationSnapshot,
    MetricSnapshot,
    MetricSourceSnapshot,
    Paper,
    PaperSourceMetric,
)
from timpapers.services.bibliography import BibliographyEntry
from timpapers.services.clients import BibliographyClient, CrossrefClient, OpenAlexClient, ScholarlyClient, SemanticScholarClient
from timpapers.services.metrics import PaperMetricInput, compute_h_index, compute_i10_index
from timpapers.services.normalization import (
    normalize_bibliography_entry,
    normalize_crossref_work,
    normalize_openalex_doi_work,
    normalize_openalex_work,
    normalize_scholarly_work,
    normalize_semanticscholar_work,
)

logger = logging.getLogger(__name__)
SOURCE_HIGHEST = "highest"
SOURCE_CROSSREF = "crossref"
SOURCE_OPENALEX = "openalex"
SOURCE_SEMANTIC_SCHOLAR = "semanticscholar"
SOURCE_SCHOLARLY = "scholarly"
TRACKED_SOURCES = (SOURCE_CROSSREF, SOURCE_OPENALEX, SOURCE_SEMANTIC_SCHOLAR, SOURCE_SCHOLARLY)


@dataclass(slots=True)
class SyncSummary:
    """Summary returned after a sync operation."""

    synced_papers: int
    started_at: datetime
    finished_at: datetime


def sync_author(db: Session, author_id: int) -> SyncSummary:
    """Sync one author's works and store snapshots and metric checkpoints."""

    author = db.get(Author, author_id)
    if author is None:
        raise ValueError(f"Author {author_id} not found")

    started = datetime.now(timezone.utc)
    settings = get_settings()
    if settings.author_bibliography_url and author.full_name == settings.author_name.strip():
        count = _sync_author_from_bibliography(db, author, settings.author_bibliography_url)
    else:
        if not author.openalex_id:
            raise ValueError("OpenAlex ID is required for legacy sync")
        count = _sync_author_from_openalex(db, author)

    _store_metric_snapshot(db, author.id)
    db.commit()

    finished = datetime.now(timezone.utc)
    logger.info("Sync completed for author=%s count=%s", author.id, count)
    return SyncSummary(synced_papers=count, started_at=started, finished_at=finished)


def _sync_author_from_openalex(db: Session, author: Author) -> int:
    """Legacy OpenAlex sync path retained for older author records."""

    works = asyncio.run(OpenAlexClient().fetch_author_works(author.openalex_id))
    count = 0

    for raw_work in works:
        normalized = normalize_openalex_work(raw_work)
        paper = _find_existing_paper(db, author.id, str(normalized["external_work_id"]), normalized["doi"])

        if paper is None:
            paper = Paper(
                author_id=author.id,
                openalex_work_id=str(normalized["external_work_id"]),
                title=str(normalized["title"]),
                author_list=str(normalized["author_list"]),
                citation_count=0,
                first_seen_citation_count=0,
                last_seen_citation_count=0,
            )
            db.add(paper)
            db.flush()
        _apply_paper_update(paper, normalized)
        _upsert_source_metric(db, paper, SOURCE_OPENALEX, int(normalized["citation_count"]))
        db.flush()
        _refresh_paper_citation_count(db, paper, fallback_count=int(normalized["citation_count"]))
        db.add(CitationSnapshot(paper_id=paper.id, citation_count=paper.citation_count))
        count += 1

    return count


def _sync_author_from_bibliography(db: Session, author: Author, bibliography_url: str) -> int:
    """Sync one configured author from a public BibTeX bibliography plus Crossref."""

    entries = asyncio.run(BibliographyClient().fetch_entries(bibliography_url))
    if not entries:
        raise ValueError("Bibliography sync returned no entries; refusing to overwrite local data")
    doi_metadata = asyncio.run(_fetch_doi_metadata(entries))

    seen_keys: set[str] = set()
    count = 0
    for entry in entries:
        normalized, source_counts = _normalize_bibliography_work(entry, doi_metadata)
        external_work_id = str(normalized["external_work_id"])
        seen_keys.add(external_work_id)

        paper = _find_existing_paper(db, author.id, external_work_id, normalized["doi"])
        if paper is None:
            paper = Paper(
                author_id=author.id,
                openalex_work_id=external_work_id,
                title=str(normalized["title"]),
                author_list=str(normalized["author_list"]),
                citation_count=0,
                first_seen_citation_count=0,
                last_seen_citation_count=0,
            )
            db.add(paper)
            db.flush()

        _apply_paper_update(paper, normalized)
        _sync_source_metrics(db, paper, source_counts)
        db.flush()
        _refresh_paper_citation_count(db, paper, fallback_count=int(normalized.get("citation_count") or 0))
        db.add(CitationSnapshot(paper_id=paper.id, citation_count=paper.citation_count))
        count += 1

    stale_papers = db.execute(select(Paper).where(Paper.author_id == author.id)).scalars().all()
    for paper in stale_papers:
        if paper.openalex_work_id not in seen_keys:
            db.delete(paper)

    db.flush()
    return count


def _normalize_bibliography_work(
    entry: BibliographyEntry,
    doi_metadata: dict[str, dict[str, dict[str, object] | None]],
) -> tuple[dict[str, object], dict[str, int]]:
    """Merge DOI-based metadata sources for one bibliography entry."""

    merged = normalize_bibliography_entry(entry)
    if not entry.doi:
        return merged, {}

    source_payloads = doi_metadata.get(entry.doi.lower(), {})
    candidates = [merged]
    source_counts: dict[str, int] = {}

    crossref_work = source_payloads.get("crossref")
    if isinstance(crossref_work, dict):
        crossref_normalized = normalize_crossref_work(crossref_work, entry)
        candidates.append(crossref_normalized)
        source_counts[SOURCE_CROSSREF] = _citation_value(crossref_normalized)

    openalex_work = source_payloads.get("openalex")
    if isinstance(openalex_work, dict):
        openalex_normalized = normalize_openalex_doi_work(openalex_work, entry)
        candidates.append(openalex_normalized)
        source_counts[SOURCE_OPENALEX] = _citation_value(openalex_normalized)

    semanticscholar_work = source_payloads.get("semanticscholar")
    if isinstance(semanticscholar_work, dict):
        semanticscholar_normalized = normalize_semanticscholar_work(semanticscholar_work, entry)
        candidates.append(semanticscholar_normalized)
        source_counts[SOURCE_SEMANTIC_SCHOLAR] = _citation_value(semanticscholar_normalized)

    scholarly_work = source_payloads.get("scholarly")
    if isinstance(scholarly_work, dict):
        scholarly_normalized = normalize_scholarly_work(scholarly_work, entry)
        candidates.append(scholarly_normalized)
        source_counts[SOURCE_SCHOLARLY] = _citation_value(scholarly_normalized)

    best = candidates[0]
    for candidate in candidates[1:]:
        if _citation_value(candidate) > _citation_value(best):
            best = candidate

    merged["citation_count"] = max(_citation_value(candidate) for candidate in candidates)
    for field in ("title", "year", "doi", "venue", "author_list"):
        for candidate in (best, *candidates):
            value = candidate.get(field)
            if value not in ("", None):
                merged[field] = value
                break
    return merged, source_counts


def _find_existing_paper(db: Session, author_id: int, external_work_id: str, doi: object) -> Paper | None:
    """Resolve a local paper by stable source key or DOI."""

    paper = db.execute(
        select(Paper).where(
            Paper.author_id == author_id,
            Paper.openalex_work_id == external_work_id,
        )
    ).scalar_one_or_none()
    if paper is not None:
        return paper

    if isinstance(doi, str) and doi:
        paper = db.execute(
            select(Paper).where(
                Paper.author_id == author_id,
                Paper.doi == doi,
            )
        ).scalar_one_or_none()
        if paper is not None:
            paper.openalex_work_id = external_work_id
            return paper
    return None


def _apply_paper_update(paper: Paper, normalized: dict[str, object]) -> None:
    """Apply normalized metadata fields to an existing paper row."""

    paper.title = str(normalized["title"])
    paper.year = int(normalized["year"]) if normalized["year"] else None
    paper.doi = normalized["doi"] if isinstance(normalized["doi"], str) or normalized["doi"] is None else None
    paper.venue = normalized["venue"] if isinstance(normalized["venue"], str) or normalized["venue"] is None else None
    paper.author_list = str(normalized["author_list"])
    paper.openalex_work_id = str(normalized["external_work_id"])


def _sync_source_metrics(db: Session, paper: Paper, source_counts: dict[str, int]) -> None:
    """Upsert current citation counts for each source on one paper."""

    for source, citation_count in source_counts.items():
        _upsert_source_metric(db, paper, source, citation_count)


def _upsert_source_metric(db: Session, paper: Paper, source: str, citation_count: int) -> None:
    """Create or update one paper/source citation row."""

    metric = db.execute(
        select(PaperSourceMetric).where(
            PaperSourceMetric.paper_id == paper.id,
            PaperSourceMetric.source == source,
        )
    ).scalar_one_or_none()
    if metric is None:
        metric = PaperSourceMetric(
            paper_id=paper.id,
            source=source,
            citation_count=0,
            first_seen_citation_count=0,
            last_seen_citation_count=0,
        )
        db.add(metric)

    metric.last_seen_citation_count = metric.citation_count
    metric.citation_count = citation_count
    if metric.first_seen_citation_count == 0 and citation_count:
        metric.first_seen_citation_count = citation_count


def _refresh_paper_citation_count(db: Session, paper: Paper, *, fallback_count: int) -> None:
    """Refresh the paper-level citation total from persisted per-source metrics."""

    source_metrics = db.execute(select(PaperSourceMetric).where(PaperSourceMetric.paper_id == paper.id)).scalars().all()
    next_citations = max((metric.citation_count for metric in source_metrics), default=fallback_count)
    paper.last_seen_citation_count = paper.citation_count
    paper.citation_count = next_citations
    if paper.first_seen_citation_count == 0 and next_citations:
        paper.first_seen_citation_count = next_citations


def _store_metric_snapshot(db: Session, author_id: int) -> None:
    """Persist one aggregate metric snapshot after sync completion."""

    author_papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    citations = [p.citation_count for p in author_papers]
    db.add(
        MetricSnapshot(
            author_id=author_id,
            total_citations=sum(citations),
            h_index=compute_h_index(citations),
            i10_index=compute_i10_index(citations),
            paper_count=len(citations),
        )
    )
    _store_source_metric_snapshots(db, author_id, author_papers)


def _store_source_metric_snapshots(db: Session, author_id: int, papers: list[Paper]) -> None:
    """Persist per-source aggregate metric snapshots after sync completion."""

    for source in (SOURCE_HIGHEST, *TRACKED_SOURCES):
        counts = _counts_for_source(papers, source)
        db.add(
            MetricSourceSnapshot(
                author_id=author_id,
                source=source,
                total_citations=sum(counts),
                h_index=compute_h_index(counts),
                i10_index=compute_i10_index(counts),
                paper_count=len(papers),
            )
        )


async def _fetch_doi_metadata(entries: list[BibliographyEntry]) -> dict[str, dict[str, dict[str, object] | None]]:
    """Fetch DOI metadata from Crossref, OpenAlex, and Semantic Scholar."""

    dois = [entry.doi for entry in entries if entry.doi]
    if not dois:
        return {}

    crossref_results, openalex_results, semanticscholar_results, scholarly_results = await asyncio.gather(
        CrossrefClient().fetch_works(dois),
        OpenAlexClient().fetch_works_by_doi(dois),
        SemanticScholarClient().fetch_works_by_doi(dois),
        ScholarlyClient().fetch_works_by_doi(dois),
    )
    merged: dict[str, dict[str, dict[str, object] | None]] = {}
    for doi in dict.fromkeys(doi.lower() for doi in dois):
        merged[doi] = {
            "crossref": crossref_results.get(doi),
            "openalex": openalex_results.get(doi),
            "semanticscholar": semanticscholar_results.get(doi),
            "scholarly": scholarly_results.get(doi),
        }
    return merged


def _citation_value(normalized: dict[str, object]) -> int:
    """Read a normalized citation count for source comparison."""

    value = normalized.get("citation_count")
    return int(value) if isinstance(value, int) else 0


def _counts_for_source(papers: list[Paper], source: str) -> list[int]:
    """Extract current citation counts for one source across an author's papers."""

    if source == SOURCE_HIGHEST:
        return [paper.citation_count for paper in papers]

    counts: list[int] = []
    for paper in papers:
        metric = next((metric for metric in paper.source_metrics if metric.source == source), None)
        counts.append(metric.citation_count if metric is not None else 0)
    return counts


def get_metric_inputs(papers: list[Paper]) -> list[PaperMetricInput]:
    """Convert persisted papers to metric computation inputs."""

    return [PaperMetricInput(paper_id=p.id, title=p.title, citations=p.citation_count) for p in papers]
