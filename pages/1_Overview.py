"""Overview page with events and quick highlights."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import events_dataframe, get_active_author, metrics_dict, papers_dataframe


def load_overview(author_id: int):
    with session_scope() as db:
        return metrics_dict(db, author_id), papers_dataframe(db, author_id), events_dataframe(db, author_id, limit=10)


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
metrics, papers, events = load_overview(author.id)

cards = st.columns(3)
cards[0].metric("Total citations", f"{metrics['total_citations']:,}")
cards[1].metric("h-index", metrics["h_index"])
cards[2].metric("i10-index", metrics["i10_index"])
st.caption(f"Current h-index source: {metrics['h_index_source']}.")

st.subheader("Highlights")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Top cited**")
    st.dataframe(
        papers.sort_values("citations", ascending=False).head(5)[["title", "citations", "year"]],
        hide_index=True,
        width="stretch",
    )
with col2:
    st.markdown("**Fastest growing (last sync)**")
    st.dataframe(
        papers.sort_values("citation_gain_30d", ascending=False).head(5)[["title", "citation_gain_30d", "citations"]],
        hide_index=True,
        width="stretch",
    )

st.subheader("Recent events")
st.dataframe(events, hide_index=True, width="stretch")
