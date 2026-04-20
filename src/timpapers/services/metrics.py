"""Metric and h-index frontier computation utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PaperMetricInput:
    """Normalized paper input used for all metric calculations."""

    paper_id: int
    title: str
    citations: int


def compute_h_index(citations: list[int]) -> int:
    """Compute h-index from a list of citation counts."""

    sorted_cites = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(sorted_cites, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def compute_i10_index(citations: list[int]) -> int:
    """Compute i10-index from citation counts."""

    return sum(1 for c in citations if c >= 10)


def hindex_frontier(papers: list[PaperMetricInput]) -> dict[str, object]:
    """Compute h-index contribution and frontier grouping data."""

    ranked = sorted(papers, key=lambda p: p.citations, reverse=True)
    h_value = compute_h_index([p.citations for p in ranked])

    rows: list[dict[str, object]] = []
    contributors: list[dict[str, object]] = []
    safe: list[dict[str, object]] = []
    near: list[dict[str, object]] = []
    far: list[dict[str, object]] = []

    for idx, paper in enumerate(ranked, start=1):
        if idx <= h_value:
            group = "contributor"
        elif paper.citations >= h_value:
            group = "safe"
        elif h_value - paper.citations <= 3:
            group = "near_miss"
        else:
            group = "far_below"

        delta = max(0, h_value + 1 - paper.citations)
        row = {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "rank": idx,
            "citations": paper.citations,
            "group": group,
            "delta_to_next_h": delta,
        }
        rows.append(row)
        if group == "contributor":
            contributors.append(row)
        elif group == "safe":
            safe.append(row)
        elif group == "near_miss":
            near.append(row)
        else:
            far.append(row)

    return {
        "h_index": h_value,
        "threshold": h_value,
        "contributors": contributors,
        "safe_above_threshold": safe,
        "near_misses": sorted(near, key=lambda r: r["delta_to_next_h"]),
        "far_below": far,
        "ranked_papers": rows,
    }
