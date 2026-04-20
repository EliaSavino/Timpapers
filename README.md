# TimPapers

Native iOS + FastAPI system for a single professor/PI to track publications, citations, h-index, i10-index, and h-index frontier opportunities.

## Monorepo layout

- `backend/` — Python 3.12 FastAPI service with SQLAlchemy persistence, metric computation, scheduled refresh jobs, and events.
- `ios-app/` — SwiftUI iPhone app + WidgetKit extension source files.

## Data sources

- Primary: OpenAlex
- Secondary/fallback enrichment: Semantic Scholar Academic Graph API
- Explicitly no unofficial Google Scholar scraping.

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### iOS app

Open/create an Xcode project and include files under `ios-app/` for main app + widget extension targets.
