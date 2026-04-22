"""Framework-agnostic analytics and view-model builders for the dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from timpapers.config import get_settings
from timpapers.models import Author, AuthorMetricOverride, Event, MetricSnapshot, MetricSourceSnapshot, Paper, PaperSourceMetric
from timpapers.services.metrics import PaperMetricInput, compute_h_index, compute_i10_index, hindex_frontier
from timpapers.services.sync import (
    SOURCE_CROSSREF,
    SOURCE_HIGHEST,
    SOURCE_OPENALEX,
    SOURCE_SCHOLARLY,
    SOURCE_SEMANTIC_SCHOLAR,
    get_metric_inputs,
)

SOURCE_LABELS = {
    SOURCE_HIGHEST: "Highest",
    SOURCE_CROSSREF: "Crossref",
    SOURCE_OPENALEX: "OpenAlex",
    SOURCE_SEMANTIC_SCHOLAR: "Semantic Scholar",
    SOURCE_SCHOLARLY: "Google Scholar",
}


@dataclass(slots=True)
class DashboardMetrics:
    """High-level KPI values for the overview page."""

    total_citations: int
    h_index: int
    i10_index: int
    h_index_source: str
    citation_source: str
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


def get_active_author(db: Session) -> Author | None:
    """Return the configured author record, creating it when configuration is present."""

    settings = get_settings()
    configured_name = settings.author_name.strip()
    if not configured_name:
        authors = list_authors(db)
        return authors[0] if authors else None

    author = (
        db.execute(select(Author).where(Author.full_name == configured_name).order_by(Author.id.desc()))
        .scalars()
        .first()
    )
    if author is not None:
        return author

    author = Author(full_name=configured_name, openalex_id=None)
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


def get_metric_override(db: Session, author_id: int) -> AuthorMetricOverride | None:
    """Return any stored manual metric override for one author."""

    return db.execute(select(AuthorMetricOverride).where(AuthorMetricOverride.author_id == author_id)).scalar_one_or_none()


def save_metric_override(
    db: Session,
    author_id: int,
    *,
    source: str,
    h_index: int | None,
    i10_index: int | None = None,
) -> AuthorMetricOverride | None:
    """Create, update, or clear a metric override for one author."""

    override = get_metric_override(db, author_id)
    if h_index is None and i10_index is None:
        if override is not None:
            db.delete(override)
            db.commit()
        return None

    if override is None:
        override = AuthorMetricOverride(author_id=author_id)
        db.add(override)

    override.source = source
    override.h_index = h_index
    override.i10_index = i10_index
    db.commit()
    db.refresh(override)
    return override


def get_dashboard_metrics(db: Session, author_id: int) -> DashboardMetrics:
    """Compute current metrics and recent gains for one author."""

    return get_dashboard_metrics_for_source(db, author_id, SOURCE_HIGHEST)


def available_citation_sources(db: Session, author_id: int) -> list[str]:
    """Return citation sources available for one author, including highest."""

    rows = (
        db.execute(
            select(PaperSourceMetric.source)
            .join(Paper, Paper.id == PaperSourceMetric.paper_id)
            .where(Paper.author_id == author_id)
            .distinct()
        )
        .scalars()
        .all()
    )
    ordered = [SOURCE_HIGHEST]
    for source in (SOURCE_CROSSREF, SOURCE_OPENALEX, SOURCE_SEMANTIC_SCHOLAR, SOURCE_SCHOLARLY):
        if source in rows:
            ordered.append(source)
    return ordered


def citation_source_label(source: str) -> str:
    """Human-readable label for a citation source key."""

    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def resolve_citation_source(db: Session, author_id: int, requested_source: str | None) -> str:
    """Return a valid citation source for the current author."""

    available = available_citation_sources(db, author_id)
    if requested_source in available:
        return str(requested_source)
    return SOURCE_HIGHEST


def get_dashboard_metrics_for_source(
    db: Session,
    author_id: int,
    citation_source: str,
    *,
    include_override: bool = True,
) -> DashboardMetrics:
    """Compute current metrics and recent gains for one author from a selected source."""

    paper_metrics = _paper_metric_rows(db, author_id, citation_source)
    counts = [row["citations"] for row in paper_metrics]
    override = get_metric_override(db, author_id)
    now = datetime.now(timezone.utc)

    snapshot_source = citation_source
    snapshots = (
        db.execute(
            select(MetricSourceSnapshot)
            .where(
                MetricSourceSnapshot.author_id == author_id,
                MetricSourceSnapshot.source == snapshot_source,
                MetricSourceSnapshot.captured_at >= now - timedelta(days=31),
            )
            .order_by(MetricSourceSnapshot.captured_at.asc())
        )
        .scalars()
        .all()
    )
    by_day = {snap.captured_at.date(): snap.total_citations for snap in snapshots}

    latest = by_day.get(now.date(), sum(counts))
    prior7 = by_day.get((now - timedelta(days=7)).date(), latest)
    prior30 = by_day.get((now - timedelta(days=30)).date(), latest)

    computed_h_index = compute_h_index(counts)
    computed_i10_index = compute_i10_index(counts)
    apply_override = (
        include_override
        and citation_source == SOURCE_HIGHEST
        and override is not None
        and override.h_index is not None
    )
    effective_h_index = override.h_index if apply_override else computed_h_index
    effective_i10_index = override.i10_index if apply_override and override.i10_index is not None else computed_i10_index
    h_index_source = override.source if apply_override else citation_source_label(citation_source)

    return DashboardMetrics(
        total_citations=sum(counts),
        h_index=effective_h_index,
        i10_index=effective_i10_index,
        h_index_source=h_index_source,
        citation_source=citation_source,
        total_papers=len(paper_metrics),
        gain_7d=max(0, latest - prior7),
        gain_30d=max(0, latest - prior30),
    )


def papers_dataframe(db: Session, author_id: int) -> pd.DataFrame:
    """Return paper table enriched with h-index frontier groups."""

    return papers_dataframe_for_source(db, author_id, SOURCE_HIGHEST)


def papers_dataframe_for_source(db: Session, author_id: int, citation_source: str) -> pd.DataFrame:
    """Return paper table enriched with h-index frontier groups for one source."""

    paper_metrics = _paper_metric_rows(db, author_id, citation_source)
    if not paper_metrics:
        return pd.DataFrame(
            columns=[
                "paper_id",
                "title",
                "year",
                "venue",
                "citations",
                "citation_gain_30d",
                "rank",
                "group",
                "delta_to_next_h",
                "citation_share",
                "cumulative_citations",
                "cumulative_share",
                "counts_for_h_index",
                "counts_for_i10",
                "h_index_value",
                "h_index_line_gap",
                "metric_role",
                "citation_source",
                "citations_highest",
                "citations_crossref",
                "citations_openalex",
                "citations_semanticscholar",
                "citations_scholarly",
            ]
        )

    analysis = hindex_frontier(
        [
            PaperMetricInput(
                paper_id=row["paper"].id,
                title=row["paper"].title,
                citations=int(row["citations"]),
            )
            for row in paper_metrics
        ]
    )
    ranked = pd.DataFrame(analysis["ranked_papers"])
    paper_df = pd.DataFrame(
        [
            {
                **_paper_source_count_columns(row["paper"]),
                "paper_id": row["paper"].id,
                "title": row["paper"].title,
                "year": row["paper"].year,
                "venue": row["paper"].venue,
                "citations": row["citations"],
                "citation_gain_30d": max(0, row["gain"]),
                "citation_source": citation_source_label(citation_source),
            }
            for row in paper_metrics
        ]
    )
    merged = paper_df.merge(ranked, how="left", on=["paper_id", "title", "citations"])
    merged = merged.sort_values("rank").reset_index(drop=True)

    total_citations = int(merged["citations"].sum())
    h_index = int(analysis["h_index"])

    if total_citations:
        merged["citation_share"] = merged["citations"] / total_citations
        merged["cumulative_citations"] = merged["citations"].cumsum()
        merged["cumulative_share"] = merged["cumulative_citations"] / total_citations
    else:
        merged["citation_share"] = 0.0
        merged["cumulative_citations"] = 0
        merged["cumulative_share"] = 0.0

    merged["counts_for_h_index"] = merged["rank"] <= h_index
    merged["counts_for_i10"] = merged["citations"] >= 10
    merged["h_index_value"] = h_index
    merged["h_index_line_gap"] = merged["citations"] - merged["rank"]
    merged["metric_role"] = merged.apply(_metric_role, axis=1)
    return merged


def metric_history_dataframe(db: Session, author_id: int) -> pd.DataFrame:
    """Return historical metric snapshots ready for plotting."""

    return metric_history_dataframe_for_source(db, author_id, SOURCE_HIGHEST)


def metric_history_dataframe_for_source(db: Session, author_id: int, citation_source: str) -> pd.DataFrame:
    """Return historical metric snapshots for one citation source."""

    rows = (
        db.execute(
            select(MetricSourceSnapshot)
            .where(
                MetricSourceSnapshot.author_id == author_id,
                MetricSourceSnapshot.source == citation_source,
            )
            .order_by(MetricSourceSnapshot.captured_at.asc())
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
                "source": citation_source_label(citation_source),
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


def metrics_dict_for_source(db: Session, author_id: int, citation_source: str) -> dict[str, int | str]:
    """Dictionary wrapper for one citation source."""

    return asdict(get_dashboard_metrics_for_source(db, author_id, citation_source))


def source_comparison_dataframe(db: Session, author_id: int) -> pd.DataFrame:
    """Return current metrics side-by-side across citation sources."""

    rows = []
    for source in available_citation_sources(db, author_id):
        metrics = get_dashboard_metrics_for_source(db, author_id, source, include_override=False)
        rows.append(
            {
                "source": citation_source_label(source),
                "source_key": source,
                "total_citations": metrics.total_citations,
                "h_index": metrics.h_index,
                "i10_index": metrics.i10_index,
                "paper_count": metrics.total_papers,
            }
        )
    return pd.DataFrame(rows)


def _paper_metric_rows(db: Session, author_id: int, citation_source: str) -> list[dict[str, object]]:
    """Build current citation/gain rows per paper for one selected source."""

    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    if citation_source == SOURCE_HIGHEST:
        return [
            {
                "paper": paper,
                "citations": paper.citation_count,
                "gain": paper.citation_count - paper.last_seen_citation_count,
            }
            for paper in papers
        ]

    source_rows = (
        db.execute(
            select(PaperSourceMetric)
            .join(Paper, Paper.id == PaperSourceMetric.paper_id)
            .where(Paper.author_id == author_id, PaperSourceMetric.source == citation_source)
        )
        .scalars()
        .all()
    )
    by_paper = {row.paper_id: row for row in source_rows}
    return [
        {
            "paper": paper,
            "citations": by_paper.get(paper.id).citation_count if paper.id in by_paper else 0,
            "gain": (
                by_paper.get(paper.id).citation_count - by_paper.get(paper.id).last_seen_citation_count
                if paper.id in by_paper
                else 0
            ),
        }
        for paper in papers
    ]


def _metric_role(row: pd.Series) -> str:
    """Map one paper to the metric it currently supports most directly."""

    if bool(row["counts_for_h_index"]):
        return "h-core"
    if bool(row["counts_for_i10"]):
        return "i10 support"
    return "emerging"


def _paper_source_count_columns(paper: Paper) -> dict[str, int]:
    """Expose per-source citation counts alongside the selected citation view."""

    source_counts = {metric.source: metric.citation_count for metric in paper.source_metrics}
    return {
        "citations_highest": paper.citation_count,
        "citations_crossref": source_counts.get(SOURCE_CROSSREF, 0),
        "citations_openalex": source_counts.get(SOURCE_OPENALEX, 0),
        "citations_semanticscholar": source_counts.get(SOURCE_SEMANTIC_SCHOLAR, 0),
        "citations_scholarly": source_counts.get(SOURCE_SCHOLARLY, 0),
    }
