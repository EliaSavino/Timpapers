"""Bootstrap utilities for app startup and data refresh."""

from __future__ import annotations

from sqlalchemy.orm import Session

from timpapers.database import Base, engine
from timpapers.services.alerts import generate_alerts
from timpapers.services.sync import SyncSummary, sync_author


def initialize_database() -> None:
    """Create database tables if missing."""

    Base.metadata.create_all(bind=engine)


def refresh_author_data(db: Session, author_id: int) -> tuple[SyncSummary, int]:
    """Run sync plus alert generation and return operation summary."""

    summary = sync_author(db, author_id)
    generated_events = generate_alerts(db, author_id)
    return summary, generated_events
