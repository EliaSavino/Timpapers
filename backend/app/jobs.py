"""Scheduled refresh jobs."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Author
from app.services.alerts import generate_alerts
from app.services.sync import sync_author

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def refresh_all_authors_job() -> None:
    """Scheduled job to refresh all tracked authors safely and idempotently."""

    logger.info("Running scheduled refresh job")
    with SessionLocal() as db:
        authors = db.execute(select(Author)).scalars().all()
        for author in authors:
            try:
                summary = sync_author(db, author.id)
                generated = generate_alerts(db, author.id)
                logger.info(
                    "Author refresh complete author=%s papers=%s events=%s",
                    author.id,
                    summary.synced_papers,
                    generated,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Refresh failed for author=%s", author.id)


def start_scheduler() -> None:
    """Start APScheduler with configured interval."""

    settings = get_settings()
    scheduler.add_job(
        refresh_all_authors_job,
        trigger="interval",
        minutes=settings.refresh_interval_minutes,
        id="refresh_authors",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """Stop scheduler during graceful shutdown."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
