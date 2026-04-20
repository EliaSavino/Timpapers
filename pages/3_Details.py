"""Detailed tables and exports."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.database import session_scope
from timpapers.services.analytics import list_authors, papers_dataframe


@st.cache_data(ttl=300)
def load_details(author_id: int):
    with session_scope() as db:
        return papers_dataframe(db, author_id)


st.header("Details")
with session_scope() as db:
    authors = list_authors(db)
if not authors:
    st.info("No authors found yet.")
    st.stop()

selected = st.sidebar.selectbox("Author", authors, format_func=lambda a: f"{a.full_name} (#{a.id})")
papers = load_details(selected.id)

if papers.empty:
    st.info("No papers synced yet for this author.")
    st.stop()

group = st.segmented_control("Frontier group", options=["all", "contributor", "safe", "near_miss", "far_below"], default="all")
if group != "all":
    papers = papers[papers["group"] == group]

st.dataframe(
    papers[["title", "year", "venue", "citations", "citation_gain_30d", "group", "delta_to_next_h"]],
    use_container_width=True,
    hide_index=True,
)

csv_data = papers.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered table (CSV)", data=csv_data, file_name="timpapers_papers.csv", mime="text/csv")
