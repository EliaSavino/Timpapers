"""HTTP API routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Author, CitationSnapshot, Event, Paper
from app.schemas import (
    AuthorCandidate,
    AuthorResolveRequest,
    AuthorResponse,
    CitationPoint,
    DashboardResponse,
    EventResponse,
    HIndexAnalysisResponse,
    HealthResponse,
    MetricsResponse,
    PaperDetail,
    PaperSummary,
    SyncRequest,
    SyncResponse,
)
from app.services.alerts import generate_alerts
from app.services.clients import OpenAlexClient, SemanticScholarClient
from app.services.metrics import compute_h_index, compute_i10_index, hindex_frontier
from app.services.sync import get_metric_inputs, sync_author

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/author", response_model=AuthorResponse)
def get_author(db: Session = Depends(get_db)) -> AuthorResponse:
    author = db.execute(select(Author).order_by(Author.id.desc())).scalar_one_or_none()
    if author is None:
        raise HTTPException(status_code=404, detail="No author configured")
    return AuthorResponse.model_validate(author, from_attributes=True)


@router.post("/author/resolve", response_model=list[AuthorCandidate])
async def resolve_author(payload: AuthorResolveRequest, db: Session = Depends(get_db)) -> list[AuthorCandidate]:
    openalex_candidates = await OpenAlexClient().search_author(payload.full_name)
    semantic_candidates = await SemanticScholarClient().search_author(payload.full_name)

    candidates: list[AuthorCandidate] = []
    for c in openalex_candidates:
        candidates.append(
            AuthorCandidate(
                source="openalex",
                id=str(c.get("id")),
                display_name=str(c.get("display_name")),
                works_count=c.get("works_count"),
                cited_by_count=c.get("cited_by_count"),
            )
        )
    for c in semantic_candidates:
        candidates.append(
            AuthorCandidate(
                source="semanticscholar",
                id=str(c.get("authorId")),
                display_name=str(c.get("name")),
                works_count=c.get("paperCount"),
                cited_by_count=c.get("citationCount"),
            )
        )

    if payload.openalex_id or payload.semanticscholar_id:
        author = db.execute(select(Author).where(Author.full_name == payload.full_name)).scalar_one_or_none()
        if author is None:
            author = Author(full_name=payload.full_name)
            db.add(author)
        author.openalex_id = payload.openalex_id or author.openalex_id
        author.semanticscholar_id = payload.semanticscholar_id or author.semanticscholar_id
        db.commit()

    return candidates


@router.post("/sync", response_model=SyncResponse)
def sync(payload: SyncRequest, db: Session = Depends(get_db)) -> SyncResponse:
    summary = sync_author(db, payload.author_id)
    generated = generate_alerts(db, payload.author_id)
    return SyncResponse(
        synced_papers=summary.synced_papers,
        generated_events=generated,
        started_at=summary.started_at,
        finished_at=summary.finished_at,
    )


def _compute_metrics(db: Session, author_id: int) -> MetricsResponse:
    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    counts = [p.citation_count for p in papers]
    now = datetime.now(timezone.utc)
    snapshots = db.execute(
        select(CitationSnapshot, Paper)
        .join(Paper, Paper.id == CitationSnapshot.paper_id)
        .where(Paper.author_id == author_id, CitationSnapshot.captured_at >= now - timedelta(days=31))
    ).all()

    by_day: dict[datetime.date, int] = defaultdict(int)
    for snap, _ in snapshots:
        by_day[snap.captured_at.date()] += snap.citation_count

    latest = by_day.get(now.date(), sum(counts))
    prior7 = by_day.get((now - timedelta(days=7)).date(), latest)
    prior30 = by_day.get((now - timedelta(days=30)).date(), latest)

    return MetricsResponse(
        total_citations=sum(counts),
        paper_count=len(papers),
        h_index=compute_h_index(counts),
        i10_index=compute_i10_index(counts),
        gain_7d=max(0, latest - prior7),
        gain_30d=max(0, latest - prior30),
    )


@router.get("/metrics", response_model=MetricsResponse)
def metrics(author_id: int, db: Session = Depends(get_db)) -> MetricsResponse:
    return _compute_metrics(db, author_id)


@router.get("/metrics/hindex-analysis", response_model=HIndexAnalysisResponse)
def hindex_analysis(author_id: int, db: Session = Depends(get_db)) -> HIndexAnalysisResponse:
    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    analysis = hindex_frontier(get_metric_inputs(papers))
    return HIndexAnalysisResponse(**analysis)


@router.get("/papers", response_model=list[PaperSummary])
def papers(author_id: int, db: Session = Depends(get_db)) -> list[PaperSummary]:
    analysis = hindex_frontier(get_metric_inputs(db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()))
    h_value = analysis["h_index"]
    result: list[PaperSummary] = []
    for row in analysis["ranked_papers"]:
        paper = db.get(Paper, row["paper_id"])
        if paper is None:
            continue
        result.append(
            PaperSummary(
                id=paper.id,
                title=paper.title,
                year=paper.year,
                venue=paper.venue,
                citations=paper.citation_count,
                citation_gain_30d=max(0, paper.citation_count - paper.last_seen_citation_count),
                contributes_to_h_index=row["group"] == "contributor",
                near_h_threshold=row["group"] == "near_miss" or (paper.citation_count < h_value and h_value - paper.citation_count <= 2),
            )
        )
    return result


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def paper_detail(paper_id: int, db: Session = Depends(get_db)) -> PaperDetail:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    author_papers = db.execute(select(Paper).where(Paper.author_id == paper.author_id)).scalars().all()
    analysis = hindex_frontier(get_metric_inputs(author_papers))
    row = next((r for r in analysis["ranked_papers"] if r["paper_id"] == paper.id), None)

    history_rows = db.execute(
        select(CitationSnapshot)
        .where(CitationSnapshot.paper_id == paper.id)
        .order_by(CitationSnapshot.captured_at.asc())
    ).scalars()

    badges = []
    if row:
        if row["group"] == "contributor":
            badges.append("Counts toward h-index")
        if row["group"] == "safe":
            badges.append("Above threshold")
        if row["delta_to_next_h"] > 0:
            badges.append(f"Needs {row['delta_to_next_h']} more citations to affect h-index")

    doi = paper.doi
    doi_url = f"https://doi.org/{doi}" if doi else None

    return PaperDetail(
        id=paper.id,
        title=paper.title,
        authors=[a.strip() for a in paper.author_list.split(",") if a.strip()],
        year=paper.year,
        venue=paper.venue,
        doi=paper.doi,
        doi_url=doi_url,
        openalex_url=f"https://openalex.org/{paper.openalex_work_id.split('/')[-1]}",
        semanticscholar_url=f"https://www.semanticscholar.org/paper/{paper.semanticscholar_paper_id}" if paper.semanticscholar_paper_id else None,
        citations=paper.citation_count,
        contribution_badges=badges,
        history=[CitationPoint(date=s.captured_at.date(), total_citations=s.citation_count) for s in history_rows],
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(author_id: int, db: Session = Depends(get_db)) -> DashboardResponse:
    m = _compute_metrics(db, author_id)
    paper_summaries = papers(author_id, db)
    top_cited = sorted(paper_summaries, key=lambda p: p.citations, reverse=True)[:5]
    fastest = sorted(paper_summaries, key=lambda p: p.citation_gain_30d, reverse=True)[:5]

    events = db.execute(
        select(Event).where(Event.author_id == author_id).order_by(Event.created_at.desc()).limit(10)
    ).scalars()

    return DashboardResponse(
        total_citations=m.total_citations,
        h_index=m.h_index,
        i10_index=m.i10_index,
        total_papers=m.paper_count,
        gain_7d=m.gain_7d,
        gain_30d=m.gain_30d,
        growth=[],
        top_cited=top_cited,
        fastest_growing=fastest,
        recent_events=[EventResponse.model_validate(e, from_attributes=True) for e in events],
    )


@router.get("/events", response_model=list[EventResponse])
def events(author_id: int, db: Session = Depends(get_db)) -> list[EventResponse]:
    rows = db.execute(select(Event).where(Event.author_id == author_id).order_by(Event.created_at.desc())).scalars().all()
    return [EventResponse.model_validate(e, from_attributes=True) for e in rows]
