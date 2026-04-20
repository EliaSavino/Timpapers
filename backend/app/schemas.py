"""Pydantic DTOs for API contract stability."""

from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, Field, HttpUrl


class HealthResponse(BaseModel):
    status: str = "ok"


class AuthorResolveRequest(BaseModel):
    full_name: str
    openalex_id: str | None = None
    semanticscholar_id: str | None = None


class AuthorCandidate(BaseModel):
    source: str
    id: str
    display_name: str
    works_count: int | None = None
    cited_by_count: int | None = None


class AuthorResponse(BaseModel):
    id: int
    full_name: str
    openalex_id: str | None
    semanticscholar_id: str | None


class SyncRequest(BaseModel):
    author_id: int


class SyncResponse(BaseModel):
    synced_papers: int
    generated_events: int
    started_at: datetime
    finished_at: datetime


class CitationPoint(BaseModel):
    date: date
    total_citations: int


class PaperSummary(BaseModel):
    id: int
    title: str
    year: int | None
    venue: str | None
    citations: int
    citation_gain_30d: int
    contributes_to_h_index: bool
    near_h_threshold: bool


class PaperDetail(BaseModel):
    id: int
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    doi: str | None
    doi_url: HttpUrl | None
    openalex_url: HttpUrl | None
    semanticscholar_url: HttpUrl | None
    citations: int
    contribution_badges: list[str]
    history: list[CitationPoint]


class DashboardResponse(BaseModel):
    total_citations: int
    h_index: int
    i10_index: int
    total_papers: int
    gain_7d: int
    gain_30d: int
    growth: list[CitationPoint]
    top_cited: list[PaperSummary]
    fastest_growing: list[PaperSummary]
    recent_events: list["EventResponse"]


class HIndexBin(BaseModel):
    paper_id: int
    title: str
    rank: int
    citations: int
    group: str = Field(description="contributor|safe|near_miss|far_below")
    delta_to_next_h: int


class HIndexAnalysisResponse(BaseModel):
    h_index: int
    threshold: int
    contributors: list[HIndexBin]
    safe_above_threshold: list[HIndexBin]
    near_misses: list[HIndexBin]
    far_below: list[HIndexBin]
    ranked_papers: list[HIndexBin]


class MetricsResponse(BaseModel):
    total_citations: int
    paper_count: int
    h_index: int
    i10_index: int
    gain_7d: int
    gain_30d: int


class EventResponse(BaseModel):
    id: int
    event_type: str
    message: str
    paper_id: int | None
    event_value: float | None
    created_at: datetime


DashboardResponse.model_rebuild()
