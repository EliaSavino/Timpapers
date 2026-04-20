"""Analysis page with deeper charts."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.plotting.charts import make_frontier_chart, make_hindex_trend
from timpapers.services.analytics import get_active_author, metric_history_dataframe, papers_dataframe


def load_analysis(author_id: int):
    with session_scope() as db:
        return metric_history_dataframe(db, author_id), papers_dataframe(db, author_id)


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
history, papers = load_analysis(author.id)

st.caption("h-index trend is based on synced bibliography and DOI-source citation snapshots.")
st.plotly_chart(make_hindex_trend(history), width="stretch", key="hindex_trend_chart")
st.plotly_chart(make_frontier_chart(papers), width="stretch", key="frontier_chart")
