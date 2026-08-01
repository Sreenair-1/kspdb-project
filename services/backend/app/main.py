from fastapi import FastAPI

from app.api import incidents, registry, system
from app.lifespan import lifespan

app = FastAPI(
    title="KSPDB Fault Localization API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(system.router)
app.include_router(registry.router)
app.include_router(incidents.router)
