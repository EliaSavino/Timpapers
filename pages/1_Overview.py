"""Overview page with events and quick highlights."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import (
    available_citation_sources,
    citation_source_label,
    events_dataframe,
    get_active_author,
    metrics_dict_for_source,
    papers_dataframe_for_source,
)


def load_overview(author_id: int, citation_source: str):
    with session_scope() as db:
        return (
            metrics_dict_for_source(db, author_id, citation_source),
            papers_dataframe_for_source(db, author_id, citation_source),
            events_dataframe(db, author_id, limit=10),
        )


st.header("Overview")
settings = get_settings()
if not settings.author_name.strip() or not settings.author_bibliography_url.strip():
    st.info("Add the author name and bibliography URL to the config file before using this page.")
    st.stop()

with session_scope() as db:
    author = get_active_author(db)
if author is None:
    st.info("No configured author is available yet.")
    st.stop()

st.sidebar.markdown(f"**Author**  \n{author.full_name}")
with session_scope() as db:
    available_sources = available_citation_sources(db, author.id)
default_source = "highest"
current_source = st.session_state.get("citation_source", default_source)
if current_source not in available_sources:
    current_source = default_source
citation_source = st.sidebar.selectbox(
    "Citation source",
    available_sources,
    index=available_sources.index(current_source),
    format_func=citation_source_label,
    key="citation_source",
)
metrics, papers, events = load_overview(author.id, citation_source)

cards = st.columns(3)
cards[0].metric("Total citations", f"{metrics['total_citations']:,}")
cards[1].metric("h-index", metrics["h_index"])
cards[2].metric("i10-index", metrics["i10_index"])
st.caption(f"Current h-index source: {metrics['h_index_source']}.")

st.subheader("Highlights")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Top cited**")
    top_cited = papers.sort_values("citations", ascending=False).head(5).copy()
    top_cited["share_pct"] = (top_cited["citation_share"] * 100).round(1)
    st.dataframe(
        top_cited[["title", "citations", "share_pct", "metric_role", "year"]],
        hide_index=True,
        width="stretch",
    )
with col2:
    st.markdown("**Fastest growing (last sync)**")
    fastest = papers.sort_values("citation_gain_30d", ascending=False).head(5).copy()
    fastest["share_pct"] = (fastest["citation_share"] * 100).round(1)
    st.dataframe(
        fastest[["title", "citation_gain_30d", "citations", "share_pct", "metric_role"]],
        hide_index=True,
        width="stretch",
    )

st.subheader("Recent events")
st.dataframe(events, hide_index=True, width="stretch")
