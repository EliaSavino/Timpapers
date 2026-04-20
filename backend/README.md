# TimPapers Backend

FastAPI service that aggregates publication/citation data from OpenAlex (primary) and Semantic Scholar (fallback enrichment), computes bibliometric metrics, stores history, and exposes stable REST endpoints for the iOS app.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## API

- `GET /health`
- `GET /author`
- `POST /author/resolve`
- `POST /sync`
- `GET /dashboard`
- `GET /papers`
- `GET /papers/{paper_id}`
- `GET /metrics`
- `GET /metrics/hindex-analysis`
- `GET /events`

## Storage

- SQLite for local development (default)
- PostgreSQL-ready SQLAlchemy models via `TP_DATABASE_URL`

## Refresh job

APScheduler executes periodic syncs at `TP_REFRESH_INTERVAL_MINUTES`.
