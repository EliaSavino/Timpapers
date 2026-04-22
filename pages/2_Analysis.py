"""Analysis page with deeper charts."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.plotting.charts import make_frontier_chart, make_hindex_line_scatter, make_hindex_trend
from timpapers.services.analytics import (
    available_citation_sources,
    citation_source_label,
    get_active_author,
    metric_history_dataframe_for_source,
    papers_dataframe_for_source,
)


def load_analysis(author_id: int, citation_source: str):
    with session_scope() as db:
        return metric_history_dataframe_for_source(db, author_id, citation_source), papers_dataframe_for_source(db, author_id, citation_source)


st.header("Analysis")
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
history, papers = load_analysis(author.id, citation_source)

st.caption("h-index trend is based on synced bibliography and DOI-source citation snapshots.")
st.plotly_chart(make_hindex_trend(history), width="stretch", key="hindex_trend_chart")

st.subheader("Paper contribution")
st.caption(
    "The first chart shows how much each ranked paper adds to total citations. "
    "The scatter separates papers that sit above the h-index line from those below it."
)

st.plotly_chart(make_frontier_chart(papers), width="stretch", key="frontier_chart")
st.plotly_chart(make_hindex_line_scatter(papers), width="stretch", key="hindex_line_scatter")
