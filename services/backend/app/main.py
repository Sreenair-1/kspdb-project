from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import incidents, registry, simulate, system, telemetry, tickets
from app.lifespan import lifespan

app = FastAPI(
    title="KSPDB Fault Localization API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(registry.router)
app.include_router(incidents.router)
app.include_router(telemetry.router)
app.include_router(simulate.router)
app.include_router(tickets.router)
