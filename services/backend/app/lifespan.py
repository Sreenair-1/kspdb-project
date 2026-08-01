from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import Database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database = Database(settings)
    app.state.database = database
    if settings.run_migrations_on_startup:
        database.run_migrations()
    if settings.seed_registry_on_startup:
        database.seed_registry_if_empty()
    yield
