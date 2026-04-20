"""Idempotent ingestion and synchronization service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Author, CitationSnapshot, MetricSnapshot, Paper
from app.services.clients import OpenAlexClient
from app.services.metrics import PaperMetricInput, compute_h_index, compute_i10_index
from app.services.normalization import normalize_openalex_work

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncSummary:
    synced_papers: int
    started_at: datetime
    finished_at: datetime


def sync_author(db: Session, author_id: int) -> SyncSummary:
    """Sync one author's works and store snapshots and metric checkpoints."""

    author = db.get(Author, author_id)
    if author is None:
        raise ValueError(f"Author {author_id} not found")
    if not author.openalex_id:
        raise ValueError("OpenAlex ID is required for sync")

    started = datetime.now(timezone.utc)
    logger.info("Starting sync for author=%s openalex_id=%s", author.id, author.openalex_id)

    import asyncio

    works = asyncio.run(OpenAlexClient().fetch_author_works(author.openalex_id))
    count = 0
    for raw_work in works:
        normalized = normalize_openalex_work(raw_work)
        paper = db.execute(
            select(Paper).where(
                Paper.author_id == author.id,
                Paper.openalex_work_id == normalized["openalex_work_id"],
            )
        ).scalar_one_or_none()

        if paper is None:
            paper = Paper(
                author_id=author.id,
                title=str(normalized["title"]),
                year=int(normalized["year"]) if normalized["year"] else None,
                doi=normalized["doi"],
                venue=normalized["venue"],
                author_list=str(normalized["author_list"]),
                openalex_work_id=str(normalized["openalex_work_id"]),
                citation_count=int(normalized["citation_count"]),
                first_seen_citation_count=int(normalized["citation_count"]),
                last_seen_citation_count=int(normalized["citation_count"]),
            )
            db.add(paper)
            db.flush()
        else:
            paper.last_seen_citation_count = paper.citation_count
            paper.citation_count = int(normalized["citation_count"])
            paper.title = str(normalized["title"])
            paper.venue = normalized["venue"] if isinstance(normalized["venue"], str) or normalized["venue"] is None else None

        db.add(CitationSnapshot(paper_id=paper.id, citation_count=paper.citation_count))
        count += 1

    db.flush()
    author_papers = db.execute(select(Paper).where(Paper.author_id == author.id)).scalars().all()
    citations = [p.citation_count for p in author_papers]
    db.add(
        MetricSnapshot(
            author_id=author.id,
            total_citations=sum(citations),
            h_index=compute_h_index(citations),
            i10_index=compute_i10_index(citations),
            paper_count=len(citations),
        )
    )
    db.commit()

    finished = datetime.now(timezone.utc)
    logger.info("Sync completed for author=%s count=%s", author.id, count)
    return SyncSummary(synced_papers=count, started_at=started, finished_at=finished)


def get_metric_inputs(papers: list[Paper]) -> list[PaperMetricInput]:
    """Convert persisted papers to metric computation inputs."""

    return [PaperMetricInput(paper_id=p.id, title=p.title, citations=p.citation_count) for p in papers]
