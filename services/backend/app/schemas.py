from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: bool


class RegistrySummary(BaseModel):
    feeders: int
    transformers: int
    poles: int
    instrumented_poles: int
    known_edges: int
    inferred_edges: int


class IncidentSummary(BaseModel):
    id: UUID
    incident_type: str
    status: str
    feeder_id: str | None
    dt_id: str | None
    upstream_pole_id: str | None
    downstream_pole_id: str | None
    latitude: float | None
    longitude: float | None
    pincode: str | None
    affected_poles: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    opened_at: datetime


class IncidentListResponse(BaseModel):
    items: list[IncidentSummary]
