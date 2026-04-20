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
    get_active_author,
    metric_history_dataframe,
    metrics_dict,
    papers_dataframe,
)
from timpapers.services.bootstrap import initialize_database


def load_metrics(author_id: int) -> dict[str, int]:
    """Fetch metric cards for one author."""

    with session_scope() as db:
        return metrics_dict(db, author_id)


def load_history(author_id: int):
    """Fetch metric history for one author."""

    with session_scope() as db:
        return metric_history_dataframe(db, author_id)


def load_papers(author_id: int):
    """Fetch paper-level data for one author."""

    with session_scope() as db:
        return papers_dataframe(db, author_id)


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

metrics = load_metrics(author_id)
history = load_history(author_id)
papers = load_papers(author_id)

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
st.dataframe(preview[["title", "year", "venue", "citations", "group"]], width="stretch", hide_index=True)
