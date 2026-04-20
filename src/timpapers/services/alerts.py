"""Event generation logic for milestones and h-index transitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from timpapers.models import Event, MetricSnapshot, Paper


def generate_alerts(db: Session, author_id: int) -> int:
    """Generate persisted events by comparing latest state to previous snapshots."""

    events_created = 0
    latest_two = (
        db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.author_id == author_id)
            .order_by(MetricSnapshot.captured_at.desc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    if len(latest_two) == 2 and latest_two[0].h_index > latest_two[1].h_index:
        db.add(
            Event(
                author_id=author_id,
                event_type="h_index_increase",
                message=f"h-index increased to {latest_two[0].h_index}",
                event_value=float(latest_two[0].h_index),
            )
        )
        events_created += 1

    papers = db.execute(select(Paper).where(Paper.author_id == author_id)).scalars().all()
    for paper in papers:
        gain = paper.citation_count - paper.last_seen_citation_count
        if paper.last_seen_citation_count < 100 <= paper.citation_count:
            db.add(
                Event(
                    author_id=author_id,
                    paper_id=paper.id,
                    event_type="paper_milestone",
                    message=f"'{paper.title}' crossed 100 citations",
                    event_value=100,
                )
            )
            events_created += 1
        if gain >= 5:
            db.add(
                Event(
                    author_id=author_id,
                    paper_id=paper.id,
                    event_type="paper_gain",
                    message=f"'{paper.title}' gained {gain} citations",
                    event_value=float(gain),
                )
            )
            events_created += 1

    db.commit()
    return events_created
