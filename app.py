"""TimPapers Streamlit entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.plotting.charts import make_citation_trend, make_yearly_output_chart
from timpapers.services.analytics import (
    available_citation_sources,
    citation_source_label,
    get_active_author,
    metric_history_dataframe_for_source,
    metrics_dict_for_source,
    papers_dataframe_for_source,
)
from timpapers.services.bootstrap import initialize_database


def load_metrics(author_id: int, citation_source: str) -> dict[str, int | str]:
    """Fetch metric cards for one author."""

    with session_scope() as db:
        return metrics_dict_for_source(db, author_id, citation_source)


def load_history(author_id: int, citation_source: str):
    """Fetch metric history for one author."""

    with session_scope() as db:
        return metric_history_dataframe_for_source(db, author_id, citation_source)


def load_papers(author_id: int, citation_source: str):
    """Fetch paper-level data for one author."""

    with session_scope() as db:
        return papers_dataframe_for_source(db, author_id, citation_source)


def _configured_author() -> tuple[int | None, str]:
    """Resolve the single configured author used across the app."""

    settings = get_settings()
    if not settings.author_name.strip() or not settings.author_bibliography_url.strip():
        return None, "Set the author name and bibliography URL in the config file before using the dashboard."
    with session_scope() as db:
        author = get_active_author(db)
    if author is None:
        return None, "No configured author could be resolved from the local database."
    return author.id, author.full_name


initialize_database()
st.set_page_config(page_title="TimPapers", page_icon="📚", layout="wide")
st.title("📚 TimPapers")
st.caption("A lightweight bibliometrics dashboard powered by a curated bibliography plus DOI enrichment.")

author_id, author_name = _configured_author()
if author_id is None:
    st.warning(author_name)
    st.stop()
st.sidebar.markdown(f"**Author**  \n{author_name}")
with session_scope() as db:
    available_sources = available_citation_sources(db, author_id)
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

metrics = load_metrics(author_id, citation_source)
history = load_history(author_id, citation_source)
papers = load_papers(author_id, citation_source)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total citations", f"{metrics['total_citations']:,}", delta=metrics["gain_30d"])
col2.metric("h-index", metrics["h_index"])
col3.metric("i10-index", metrics["i10_index"])
col4.metric("Papers", metrics["total_papers"], delta=metrics["gain_7d"])
st.caption(f"Current h-index source: {metrics['h_index_source']}. Trend charts are based on synced bibliography and DOI-source citation data.")

left, right = st.columns((3, 2))
with left:
    st.plotly_chart(make_citation_trend(history), width="stretch", key="citation_trend_chart")
with right:
    st.plotly_chart(make_yearly_output_chart(papers), width="stretch", key="yearly_output_chart")

st.subheader("Most cited papers")
preview = papers.sort_values("citations", ascending=False).head(10)
preview = preview.copy()
preview["share_pct"] = (preview["citation_share"] * 100).round(1)
st.dataframe(
    preview[["title", "year", "venue", "citations", "share_pct", "metric_role", "group"]],
    width="stretch",
    hide_index=True,
)
