"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine
from app.jobs import start_scheduler, stop_scheduler
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize resources and scheduler for app lifecycle."""

    configure_logging()
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(router)
