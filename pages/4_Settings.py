"""Settings and data operations page."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from timpapers.config import get_settings
from timpapers.database import session_scope
from timpapers.services.analytics import ensure_author, get_active_author, get_metric_override, save_metric_override
from timpapers.services.bootstrap import refresh_author_data
from timpapers.services.clients import OpenAlexClient


@st.cache_data(ttl=120)
def search_openalex_author(query: str) -> list[dict[str, object]]:
    """Search OpenAlex authors for setup workflow."""

    return asyncio.run(OpenAlexClient().search_author(query))


st.header("Settings / Data")
st.caption("Single-author mode: the bibliography file is the source of truth, and DOI lookups enrich each paper.")

settings = get_settings()
workspace_root = Path(__file__).resolve().parent.parent
secret_config_path = workspace_root / "author_config.secret.toml"
example_config_path = workspace_root / "author_config.example.toml"
streamlit_secret_path = workspace_root / ".streamlit" / "secrets.toml"
legacy_mode = st.query_params.get("legacy") == "1"

st.markdown(f"Example config: [author_config.example.toml]({example_config_path})")
st.write("Secret config locations:")
st.write(f"`{secret_config_path}`")
st.write(f"`{streamlit_secret_path}`")
st.code(
    "[author]\n"
    'name = "Timothy Noel"\n'
    'bibliography_url = "https://github.com/Noel-Research-Group/NRG-bibliography/blob/main/publications.bib"\n\n'
    "[app]\n"
    'openalex_api_key = ""\n'
    'crossref_mailto = "you@example.com"\n'
    "semanticscholar_enabled = true\n"
    "scholarly_enabled = false\n"
    'scholarly_proxy_mode = "free_proxies"\n'
    'scholarly_proxy_http = ""\n'
    'scholarly_proxy_https = ""\n'
    'scholarly_tor_cmd = "tor"\n'
    "scholarly_tor_sock_port = 9050\n"
    "scholarly_tor_control_port = 9051\n"
    'scholarly_tor_password = ""\n',
    language="toml",
)

if not settings.author_name.strip() or not settings.author_bibliography_url.strip():
    st.warning("No secret config was found. Create `author_config.secret.toml` or `.streamlit/secrets.toml`, then reload the app.")
    st.stop()

st.write(f"Configured author: `{settings.author_name}`")
st.write(f"Bibliography URL: `{settings.author_bibliography_url}`")
st.caption("Crossref and OpenAlex are queried DOI by DOI with backoff and low concurrency. Semantic Scholar and Google Scholar can be enabled or disabled from secret config.")
if not settings.crossref_mailto.strip():
    st.warning("Set `crossref_mailto` in the config file to use Crossref's polite pool and reduce 429 responses.")
if not (settings.openalex_api_key or "").strip():
    st.warning("Set `openalex_api_key` in the config file. OpenAlex now expects an API key for production use.")
st.write(f"Semantic Scholar enabled: `{settings.semanticscholar_enabled}`")
st.write(f"Google Scholar enabled: `{settings.scholarly_enabled}`")
if settings.scholarly_enabled:
    st.info(f"scholarly proxy mode: `{settings.scholarly_proxy_mode}`")

with session_scope() as db:
    target = get_active_author(db)

if target is None:
    st.error("The configured author could not be initialized.")
    st.stop()

if st.button("Run sync now", type="primary"):
    try:
        with st.spinner("Refreshing papers from the bibliography and DOI sources..."):
            with session_scope() as db:
                summary, generated = refresh_author_data(db, target.id)
        st.cache_data.clear()
        st.success(f"Sync complete: {summary.synced_papers} bibliography entries updated, {generated} new events.")
    except ValueError as exc:
        st.error(str(exc))

with session_scope() as db:
    metric_override = get_metric_override(db, target.id)

st.subheader("Metric override")
st.caption("Use this when Google Scholar or another source is more current than Crossref.")
default_h_index = metric_override.h_index if metric_override is not None and metric_override.h_index is not None else 0
override_enabled = st.checkbox("Use external h-index override", value=metric_override is not None and metric_override.h_index is not None)
override_source = st.text_input(
    "Override source",
    value=metric_override.source if metric_override is not None else "Google Scholar",
    disabled=not override_enabled,
)
override_h_index = st.number_input(
    "Override h-index",
    min_value=0,
    value=default_h_index,
    step=1,
    disabled=not override_enabled,
)
if st.button("Save metric override"):
    with session_scope() as db:
        save_metric_override(
            db,
            target.id,
            source=override_source or "External source",
            h_index=int(override_h_index) if override_enabled else None,
        )
    st.cache_data.clear()
    if override_enabled:
        st.success(f"Saved h-index override: {int(override_h_index)} from {override_source or 'External source'}.")
    else:
        st.success("Cleared external metric override.")

if legacy_mode:
    st.subheader("Legacy OpenAlex Controls")
    st.caption("This section is hidden by default. It is retained only for older author records.")
    name = st.text_input("Legacy author name", placeholder="e.g., Jane Doe")
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

    if st.button("Save legacy author", disabled=selected_candidate is None):
        candidate = selected_candidate
        assert candidate is not None
        with session_scope() as db:
            author = ensure_author(
                db,
                name=str(candidate.get("display_name", "Unknown")),
                openalex_id=str(candidate.get("id", "")),
            )
        st.cache_data.clear()
        st.success(f"Saved legacy author {author.full_name} (ID {author.id})")
