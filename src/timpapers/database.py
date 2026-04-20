"""Database setup and session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from timpapers.config import get_settings


class Base(DeclarativeBase):
    """Base SQLAlchemy declarative class."""


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around operations."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
