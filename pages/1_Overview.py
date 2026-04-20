"""Overview page with events and quick highlights."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.database import session_scope
from timpapers.services.analytics import events_dataframe, list_authors, metrics_dict, papers_dataframe


@st.cache_data(ttl=300)
def load_overview(author_id: int):
    with session_scope() as db:
        return metrics_dict(db, author_id), papers_dataframe(db, author_id), events_dataframe(db, author_id, limit=10)


st.header("Overview")
with session_scope() as db:
    authors = list_authors(db)

if not authors:
    st.info("Add an author from Settings / Data to populate this page.")
    st.stop()

selected = st.sidebar.selectbox("Author", authors, format_func=lambda a: f"{a.full_name} (#{a.id})")
metrics, papers, events = load_overview(selected.id)

cards = st.columns(3)
cards[0].metric("Total citations", f"{metrics['total_citations']:,}")
cards[1].metric("h-index", metrics["h_index"])
cards[2].metric("i10-index", metrics["i10_index"])

st.subheader("Highlights")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Top cited**")
    st.dataframe(
        papers.sort_values("citations", ascending=False).head(5)[["title", "citations", "year"]],
        hide_index=True,
        use_container_width=True,
    )
with col2:
    st.markdown("**Fastest growing (last sync)**")
    st.dataframe(
        papers.sort_values("citation_gain_30d", ascending=False).head(5)[["title", "citation_gain_30d", "citations"]],
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Recent events")
st.dataframe(events, hide_index=True, use_container_width=True)
