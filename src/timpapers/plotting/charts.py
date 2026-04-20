"""Plotly chart builders for Streamlit pages."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

METRIC_ROLE_COLORS = {
    "h-core": "#0f766e",
    "i10 support": "#2563eb",
    "emerging": "#f59e0b",
}

LINE_STATUS_COLORS = {
    "Above h-index line": "#059669",
    "Below h-index line": "#dc2626",
}


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
    """Build a paper-level citation contribution chart."""

    if papers.empty:
        return go.Figure()

    chart_df = papers.nsmallest(min(20, len(papers)), "rank").copy()
    chart_df["citation_share_pct"] = chart_df["citation_share"] * 100
    chart_df["cumulative_share_pct"] = chart_df["cumulative_share"] * 100

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for role, color in METRIC_ROLE_COLORS.items():
        role_df = chart_df[chart_df["metric_role"] == role]
        if role_df.empty:
            continue
        fig.add_bar(
            x=role_df["rank"],
            y=role_df["citations"],
            name=role,
            marker_color=color,
            customdata=role_df[
                [
                    "title",
                    "metric_role",
                    "group",
                    "citation_share_pct",
                    "cumulative_share_pct",
                    "year",
                ]
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Rank: %{x}<br>"
                "Citations: %{y}<br>"
                "Primary metric role: %{customdata[1]}<br>"
                "Frontier group: %{customdata[2]}<br>"
                "Share of total citations: %{customdata[3]:.1f}%<br>"
                "Cumulative share through this paper: %{customdata[4]:.1f}%<br>"
                "Year: %{customdata[5]}<extra></extra>"
            ),
        )
    fig.add_scatter(
        x=chart_df["rank"],
        y=chart_df["cumulative_share_pct"],
        name="Cumulative share",
        mode="lines+markers",
        line=dict(color="#111827", width=2),
        marker=dict(size=7),
        hovertemplate="Rank %{x}<br>Cumulative share: %{y:.1f}%<extra></extra>",
        secondary_y=True,
    )

    h_index = int(chart_df["h_index_value"].iloc[0])
    if h_index > 0:
        fig.add_vline(
            x=h_index + 0.5,
            line_dash="dash",
            line_color="#475569",
            annotation_text=f"h-core cutoff ({h_index})",
            annotation_position="top right",
        )

    fig.update_layout(
        title="Citation contribution by ranked paper",
        height=560,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
        bargap=0.18,
    )
    fig.update_xaxes(title="Paper rank by citations", dtick=1)
    fig.update_yaxes(title="Citations", secondary_y=False)
    fig.update_yaxes(title="Cumulative share of total citations", ticksuffix="%", range=[0, 100], secondary_y=True)
    return fig


def make_hindex_line_scatter(papers: pd.DataFrame) -> go.Figure:
    """Build a rank-vs-citations scatter against the h-index line."""

    if papers.empty:
        return go.Figure()

    chart_df = papers.copy()
    chart_df["line_status"] = chart_df["h_index_line_gap"].apply(
        lambda gap: "Above h-index line" if gap >= 0 else "Below h-index line"
    )
    chart_df["citation_share_pct"] = chart_df["citation_share"] * 100

    fig = px.scatter(
        chart_df,
        x="rank",
        y="citations",
        color="line_status",
        color_discrete_map=LINE_STATUS_COLORS,
        title="Papers above and below the h-index line",
    )
    fig.update_traces(
        customdata=chart_df[
            [
                "title",
                "metric_role",
                "group",
                "citation_share_pct",
                "delta_to_next_h",
                "line_status",
            ]
        ],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Rank: %{x}<br>"
            "Citations: %{y}<br>"
            "Status: %{customdata[5]}<br>"
            "Primary metric role: %{customdata[1]}<br>"
            "Frontier group: %{customdata[2]}<br>"
            "Share of total citations: %{customdata[3]:.1f}%<br>"
            "Citations needed for next h-step: %{customdata[4]}<extra></extra>"
        ),
    )

    max_rank = int(chart_df["rank"].max())
    max_citations = int(chart_df["citations"].max())
    diagonal_limit = max(max_rank, max_citations)
    fig.add_trace(
        go.Scatter(
            x=[1, diagonal_limit],
            y=[1, diagonal_limit],
            mode="lines",
            name="h-index line (citations = rank)",
            line=dict(color="#111827", dash="dot"),
            hovertemplate="h-index line<extra></extra>",
        )
    )

    h_index = int(chart_df["h_index_value"].iloc[0])
    if h_index > 0:
        fig.add_vline(x=h_index, line_dash="dash", line_color="#475569")
        fig.add_hline(
            y=h_index,
            line_dash="dash",
            line_color="#475569",
            annotation_text=f"h-index = {h_index}",
            annotation_position="top left",
        )

    fig.update_traces(marker=dict(size=11, line=dict(width=1, color="#ffffff")), selector=dict(mode="markers"))
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=50, b=10), legend_title_text="")
    fig.update_xaxes(title="Paper rank by citations", dtick=1)
    fig.update_yaxes(title="Citations")
    return fig


def make_yearly_output_chart(papers: pd.DataFrame) -> go.Figure:
    """Build paper-count and citation output by year."""

    if papers.empty:
        return go.Figure()

    grouped = (
        papers.dropna(subset=["year"])
        .groupby("year", as_index=False)
        .agg(paper_count=("paper_id", "count"), citations=("citations", "sum"), citation_share=("citation_share", "sum"))
        .sort_values("year")
    )
    if grouped.empty:
        return go.Figure()
    fig = px.bar(grouped, x="year", y="paper_count", title="Publication output by year")
    fig.add_scatter(
        x=grouped["year"],
        y=grouped["citations"],
        mode="lines+markers",
        name="citations",
        customdata=grouped["citation_share"] * 100,
        hovertemplate=(
            "Year %{x}<br>"
            "Citations from papers published this year: %{y}<br>"
            "Share of all citations: %{customdata:.1f}%<extra></extra>"
        ),
    )
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=45, b=10), yaxis_title="papers")
    return fig
