"""Plotly chart builders for Streamlit pages."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def make_citation_trend(history: pd.DataFrame) -> go.Figure:
    """Build citation trend line chart from metric snapshots."""

    if history.empty:
        return go.Figure()
    fig = px.line(
        history,
        x="captured_at",
        y="total_citations",
        markers=True,
        title="Citation trend",
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=45, b=10))
    return fig


def make_hindex_trend(history: pd.DataFrame) -> go.Figure:
    """Build h-index and i10 trend comparison chart."""

    if history.empty:
        return go.Figure()

    melted = history.melt(
        id_vars=["captured_at"],
        value_vars=["h_index", "i10_index"],
        var_name="metric",
        value_name="value",
    )
    fig = px.line(melted, x="captured_at", y="value", color="metric", markers=True, title="h-index vs i10-index")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=45, b=10), legend_title_text="")
    return fig


def make_frontier_chart(papers: pd.DataFrame) -> go.Figure:
    """Build horizontal citation chart grouped by h-index frontier status."""

    if papers.empty:
        return go.Figure()

    chart_df = papers.sort_values("citations", ascending=True).tail(25)
    fig = px.bar(
        chart_df,
        x="citations",
        y="title",
        color="group",
        orientation="h",
        title="Top papers by citations (h-index frontier grouping)",
        color_discrete_map={
            "contributor": "#2563eb",
            "safe": "#16a34a",
            "near_miss": "#f59e0b",
            "far_below": "#9ca3af",
        },
    )
    fig.update_layout(height=600, margin=dict(l=10, r=10, t=45, b=10), yaxis_title="")
    return fig


def make_yearly_output_chart(papers: pd.DataFrame) -> go.Figure:
    """Build paper-count and citation output by year."""

    if papers.empty:
        return go.Figure()

    grouped = (
        papers.dropna(subset=["year"])
        .groupby("year", as_index=False)
        .agg(paper_count=("paper_id", "count"), citations=("citations", "sum"))
        .sort_values("year")
    )
    if grouped.empty:
        return go.Figure()
    fig = px.bar(grouped, x="year", y="paper_count", title="Publication output by year")
    fig.add_scatter(x=grouped["year"], y=grouped["citations"], mode="lines+markers", name="citations")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=45, b=10), yaxis_title="papers")
    return fig
