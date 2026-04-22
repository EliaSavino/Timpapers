"""Detailed tables and exports."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import available_citation_sources, citation_source_label, get_active_author, papers_dataframe_for_source


def load_details(author_id: int, citation_source: str):
    with session_scope() as db:
        return papers_dataframe_for_source(db, author_id, citation_source)


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
papers = load_details(author.id, citation_source)

if papers.empty:
    st.info("No papers synced yet for this author.")
    st.stop()

group = st.segmented_control("Frontier group", options=["all", "contributor", "safe", "near_miss", "far_below"], default="all")
if group != "all":
    papers = papers[papers["group"] == group]

table_df = papers.copy()
table_df["share_pct"] = (table_df["citation_share"] * 100).round(1)

st.dataframe(
    table_df[
        [
            "title",
            "year",
            "venue",
            "citations",
            "citations_highest",
            "citations_crossref",
            "citations_openalex",
            "citations_semanticscholar",
            "citations_scholarly",
            "share_pct",
            "citation_gain_30d",
            "metric_role",
            "group",
            "delta_to_next_h",
        ]
    ],
    width="stretch",
    hide_index=True,
)

csv_data = papers.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered table (CSV)", data=csv_data, file_name="timpapers_papers.csv", mime="text/csv")
