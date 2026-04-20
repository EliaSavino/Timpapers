"""Detailed tables and exports."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import get_active_author, papers_dataframe


def load_details(author_id: int):
    with session_scope() as db:
        return papers_dataframe(db, author_id)


st.header("Details")
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
papers = load_details(author.id)

if papers.empty:
    st.info("No papers synced yet for this author.")
    st.stop()

group = st.segmented_control("Frontier group", options=["all", "contributor", "safe", "near_miss", "far_below"], default="all")
if group != "all":
    papers = papers[papers["group"] == group]

st.dataframe(
    papers[["title", "year", "venue", "citations", "citation_gain_30d", "group", "delta_to_next_h"]],
    width="stretch",
    hide_index=True,
)

csv_data = papers.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered table (CSV)", data=csv_data, file_name="timpapers_papers.csv", mime="text/csv")
