# TimPapers

TimPapers is now a **pure Streamlit** application for tracking publication performance for one or more researchers.

## What it does

- Pulls author/publication data from **OpenAlex**.
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

Then open the local Streamlit URL, go to **Settings / Data**, add an author, and run sync.

## Configuration

Environment variables:

- `TP_DATABASE_URL` (default `sqlite:///./timpapers.db`)
- `TP_OPENALEX_BASE_URL`
- `TP_SEMANTICSCHOLAR_BASE_URL`
- `TP_SEMANTICSCHOLAR_API_KEY`
- `TP_REQUEST_TIMEOUT_SECONDS`

## Migration notes

- Removed backend API and scheduler/web-server runtime assumptions.
- Removed iOS/Swift client code and frontend/backend split.
- Preserved and refactored reusable domain logic (metrics, normalization, sync, alerting) into framework-agnostic Python modules under `src/timpapers/services`.
