"""TimPapers Streamlit entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from timpapers.database import session_scope
from timpapers.plotting.charts import make_citation_trend, make_yearly_output_chart
from timpapers.services.analytics import (
    list_authors,
    metric_history_dataframe,
    metrics_dict,
    papers_dataframe,
)
from timpapers.services.bootstrap import initialize_database


@st.cache_data(ttl=300)
def load_metrics(author_id: int) -> dict[str, int]:
    """Fetch metric cards for one author."""

    with session_scope() as db:
        return metrics_dict(db, author_id)


@st.cache_data(ttl=300)
def load_history(author_id: int):
    """Fetch metric history for one author."""

    with session_scope() as db:
        return metric_history_dataframe(db, author_id)


@st.cache_data(ttl=300)
def load_papers(author_id: int):
    """Fetch paper-level data for one author."""

    with session_scope() as db:
        return papers_dataframe(db, author_id)


def _choose_author() -> int | None:
    """Render sidebar selector and return current author ID."""

    with session_scope() as db:
        authors = list_authors(db)

    if not authors:
        st.warning("No author configured yet. Use the **Settings / Data** page to add an author and run sync.")
        return None

    options = {f"{a.full_name} (#{a.id})": a.id for a in authors}
    labels = list(options.keys())
    default_idx = 0
    selected = st.sidebar.selectbox("Author", labels, index=default_idx)
    return options[selected]


initialize_database()
st.set_page_config(page_title="TimPapers", page_icon="📚", layout="wide")
st.title("📚 TimPapers")
st.caption("A lightweight bibliometrics dashboard powered by OpenAlex.")

author_id = _choose_author()
if author_id is None:
    st.stop()

metrics = load_metrics(author_id)
history = load_history(author_id)
papers = load_papers(author_id)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total citations", f"{metrics['total_citations']:,}", delta=metrics["gain_30d"])
col2.metric("h-index", metrics["h_index"])
col3.metric("i10-index", metrics["i10_index"])
col4.metric("Papers", metrics["total_papers"], delta=metrics["gain_7d"])

left, right = st.columns((3, 2))
with left:
    st.plotly_chart(make_citation_trend(history), use_container_width=True)
with right:
    st.plotly_chart(make_yearly_output_chart(papers), use_container_width=True)

st.subheader("Most cited papers")
preview = papers.sort_values("citations", ascending=False).head(10)
st.dataframe(preview[["title", "year", "venue", "citations", "group"]], use_container_width=True, hide_index=True)
