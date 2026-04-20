"""Framework-agnostic analytics and view-model builders for the dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from timpapers.models import Author, CitationSnapshot, Event, MetricSnapshot, Paper
from timpapers.services.metrics import compute_h_index, compute_i10_index, hindex_frontier
from timpapers.services.sync import get_metric_inputs


@dataclass(slots=True)
class DashboardMetrics:
    """High-level KPI values for the overview page."""

    total_citations: int
    h_index: int
    i10_index: int
    total_papers: int
    gain_7d: int
    gain_30d: int


def list_authors(db: Session) -> list[Author]:
    """Return tracked authors ordered by newest first."""

    return db.execute(select(Author).order_by(Author.id.desc())).scalars().all()


def ensure_author(db: Session, name: str, openalex_id: str) -> Author:
    """Create or update a local author record and return it."""

    author = db.execute(select(Author).where(Author.openalex_id == openalex_id)).scalar_one_or_none()
    if author is None:
        author = Author(full_name=name, openalex_id=openalex_id)
        db.add(author)
    else:
        author.full_name = name
    db.commit()
    db.refresh(author)
    return author


def get_dashboard_metrics(db: Session, author_id: int) -> DashboardMetrics:
    """Compute current metrics and recent gains for one author."""

    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    counts = [p.citation_count for p in papers]
    now = datetime.now(timezone.utc)

    snapshots = db.execute(
        select(CitationSnapshot, Paper)
        .join(Paper, Paper.id == CitationSnapshot.paper_id)
        .where(Paper.author_id == author_id, CitationSnapshot.captured_at >= now - timedelta(days=31))
    ).all()

    by_day: dict[datetime.date, int] = {}
    for snap, _ in snapshots:
        day = snap.captured_at.date()
        by_day[day] = by_day.get(day, 0) + snap.citation_count

    latest = by_day.get(now.date(), sum(counts))
    prior7 = by_day.get((now - timedelta(days=7)).date(), latest)
    prior30 = by_day.get((now - timedelta(days=30)).date(), latest)

    return DashboardMetrics(
        total_citations=sum(counts),
        h_index=compute_h_index(counts),
        i10_index=compute_i10_index(counts),
        total_papers=len(papers),
        gain_7d=max(0, latest - prior7),
        gain_30d=max(0, latest - prior30),
    )


def papers_dataframe(db: Session, author_id: int) -> pd.DataFrame:
    """Return paper table enriched with h-index frontier groups."""

    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    if not papers:
        return pd.DataFrame(
            columns=[
                "paper_id",
                "title",
                "year",
                "venue",
                "citations",
                "citation_gain_30d",
                "group",
                "delta_to_next_h",
            ]
        )

    analysis = hindex_frontier(get_metric_inputs(papers))
    ranked = pd.DataFrame(analysis["ranked_papers"])
    paper_df = pd.DataFrame(
        [
            {
                "paper_id": p.id,
                "title": p.title,
                "year": p.year,
                "venue": p.venue,
                "citations": p.citation_count,
                "citation_gain_30d": max(0, p.citation_count - p.last_seen_citation_count),
            }
            for p in papers
        ]
    )
    return paper_df.merge(ranked, how="left", on=["paper_id", "title", "citations"])


def metric_history_dataframe(db: Session, author_id: int) -> pd.DataFrame:
    """Return historical metric snapshots ready for plotting."""

    rows = (
        db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.author_id == author_id)
            .order_by(MetricSnapshot.captured_at.asc())
        )
        .scalars()
        .all()
    )
    return pd.DataFrame(
        [
            {
                "captured_at": row.captured_at,
                "total_citations": row.total_citations,
                "h_index": row.h_index,
                "i10_index": row.i10_index,
                "paper_count": row.paper_count,
            }
            for row in rows
        ]
    )


def events_dataframe(db: Session, author_id: int, limit: int = 50) -> pd.DataFrame:
    """Return latest events for display tables."""

    rows = (
        db.execute(
            select(Event)
            .where(Event.author_id == author_id)
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return pd.DataFrame(
        [
            {
                "created_at": row.created_at,
                "event_type": row.event_type,
                "message": row.message,
                "event_value": row.event_value,
            }
            for row in rows
        ]
    )


def metrics_dict(db: Session, author_id: int) -> dict[str, int]:
    """Dictionary wrapper for simple cache-friendly serialization."""

    return asdict(get_dashboard_metrics(db, author_id))
