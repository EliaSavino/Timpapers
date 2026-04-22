# TimPapers

TimPapers is now a **pure Streamlit** application for tracking publication performance for a curated researcher bibliography.

## What it does

- Pulls the publication list from a curated public **BibTeX bibliography**.
- Enriches DOI-backed records with **Crossref**, **OpenAlex**, **Semantic Scholar**, and optional **Google Scholar** scraping via `scholarly`, keeping the highest citation count seen for each paper.
- Stores papers, citation snapshots, and metric snapshots in SQLite (or any SQLAlchemy-supported DB URL).
- Computes core bibliometrics: total citations, h-index, i10-index, and h-index frontier groupings.
- Presents a polished dashboard with metrics, trends, analysis charts, and drill-down tables.

## Repository layout

```text
app.py
pages/
  1_Overview.py
  2_Analysis.py
  3_Details.py
  4_Settings.py
src/timpapers/
  config.py
  database.py
  models.py
  plotting/charts.py
  services/
    alerts.py
    analytics.py
    bootstrap.py
    clients.py
    metrics.py
    normalization.py
    sync.py
tests/
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
streamlit run app.py
```

Then open the local Streamlit URL, copy `author_config.example.toml` to `author_config.secret.toml` or provide the same values via `.streamlit/secrets.toml`, and run sync from **Settings / Data**.

## Configuration

Environment variables:

- `TP_DATABASE_URL` (default `sqlite:///./timpapers.db`)
- `TP_AUTHOR_NAME`
- `TP_AUTHOR_BIBLIOGRAPHY_URL`
- `TP_OPENALEX_API_KEY`
- `TP_CROSSREF_BASE_URL`
- `TP_CROSSREF_MAILTO`
- `TP_OPENALEX_BASE_URL`
- `TP_SEMANTICSCHOLAR_BASE_URL`
- `TP_SEMANTICSCHOLAR_API_KEY`
- `TP_REQUEST_TIMEOUT_SECONDS`

## Migration notes

- Removed backend API and scheduler/web-server runtime assumptions.
- Removed iOS/Swift client code and frontend/backend split.
- Preserved and refactored reusable domain logic (metrics, normalization, sync, alerting) into framework-agnostic Python modules under `src/timpapers/services`.
