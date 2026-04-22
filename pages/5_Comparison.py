"""Compare citation-derived metrics across sources."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import get_active_author, source_comparison_dataframe


def load_comparison(author_id: int):
    with session_scope() as db:
        return source_comparison_dataframe(db, author_id)


st.header("Source Comparison")
settings = get_settings()
if not settings.author_name.strip() or not settings.author_bibliography_url.strip():
    st.info("Add the author name and bibliography URL to the secret config before using this page.")
    st.stop()

with session_scope() as db:
    author = get_active_author(db)
if author is None:
    st.info("No configured author is available yet.")
    st.stop()

st.sidebar.markdown(f"**Author**  \n{author.full_name}")
comparison = load_comparison(author.id)

if comparison.empty:
    st.info("No source comparison data is available yet. Run sync first.")
    st.stop()

st.caption("Each row shows the current metrics computed from that source's citation counts. `Highest` uses the maximum citation count seen per paper across all sources.")

st.dataframe(
    comparison[["source", "h_index", "i10_index", "total_citations", "paper_count"]],
    width="stretch",
    hide_index=True,
)

chart_df = comparison.set_index("source")[["h_index", "i10_index", "total_citations"]]
st.bar_chart(chart_df)
