"""Analysis page with deeper charts."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.database import session_scope
from timpapers.plotting.charts import make_frontier_chart, make_hindex_trend
from timpapers.services.analytics import list_authors, metric_history_dataframe, papers_dataframe


@st.cache_data(ttl=300)
def load_analysis(author_id: int):
    with session_scope() as db:
        return metric_history_dataframe(db, author_id), papers_dataframe(db, author_id)


st.header("Analysis")

with session_scope() as db:
    authors = list_authors(db)
if not authors:
    st.info("No data yet. Add an author in Settings / Data.")
    st.stop()

selected = st.sidebar.selectbox("Author", authors, format_func=lambda a: f"{a.full_name} (#{a.id})")
history, papers = load_analysis(selected.id)

st.plotly_chart(make_hindex_trend(history), use_container_width=True)
st.plotly_chart(make_frontier_chart(papers), use_container_width=True)
