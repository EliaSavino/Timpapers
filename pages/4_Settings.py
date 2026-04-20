"""Settings and data operations page."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.database import session_scope
from timpapers.services.analytics import ensure_author, list_authors
from timpapers.services.bootstrap import refresh_author_data
from timpapers.services.clients import OpenAlexClient


@st.cache_data(ttl=120)
def search_openalex_author(query: str) -> list[dict[str, object]]:
    """Search OpenAlex authors for setup workflow."""

    return asyncio.run(OpenAlexClient().search_author(query))


st.header("Settings / Data")
st.caption("Minimal setup: choose an author, save, and sync.")

name = st.text_input("Author name", placeholder="e.g., Jane Doe")
if name:
    candidates = search_openalex_author(name)
else:
    candidates = []

selected_candidate = None
if candidates:
    option_map = {
        f"{c.get('display_name')} · works={c.get('works_count', 0)} · citations={c.get('cited_by_count', 0)}": c
        for c in candidates
    }
    selected_label = st.selectbox("OpenAlex match", list(option_map.keys()))
    selected_candidate = option_map[selected_label]

if st.button("Save author", type="primary", disabled=selected_candidate is None):
    candidate = selected_candidate
    assert candidate is not None
    with session_scope() as db:
        author = ensure_author(
            db,
            name=str(candidate.get("display_name", "Unknown")),
            openalex_id=str(candidate.get("id", "")),
        )
    st.success(f"Saved {author.full_name} (ID {author.id})")

with session_scope() as db:
    authors = list_authors(db)

if authors:
    target = st.selectbox("Author to sync", authors, format_func=lambda a: f"{a.full_name} (#{a.id})")
    if st.button("Run sync now"):
        with st.spinner("Refreshing papers and metrics..."):
            with session_scope() as db:
                summary, generated = refresh_author_data(db, target.id)
        st.success(f"Sync complete: {summary.synced_papers} papers updated, {generated} new events.")
else:
    st.info("No authors saved yet.")
