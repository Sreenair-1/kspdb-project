from datetime import datetime
from typing import Literal
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


class TelemetryEventRequest(BaseModel):
    device_id: str
    pole_id: str
    event: Literal["heartbeat", "power_lost", "power_restored", "boot"]
    energized: bool
    device_ts: datetime
    seq: int = Field(ge=0)
    battery_mv: int = Field(ge=0)
    rssi: int
    firmware: str


class TelemetryEventResponse(BaseModel):
    status: str
    event_id: UUID | None
    is_duplicate: bool
    is_stale: bool


class SimulateFaultRequest(BaseModel):
    fault_type: Literal["span", "dt", "feeder"]
    upstream_pole_id: str | None = None
    downstream_pole_id: str | None = None
    dt_id: str | None = None
    feeder_id: str | None = None


class SimulateRepairRequest(BaseModel):
    upstream_pole_id: str | None = None
    downstream_pole_id: str | None = None
    dt_id: str | None = None
    feeder_id: str | None = None


class SimulateResponse(BaseModel):
    affected_poles: int
    injected_events: int
    new_incidents: int
    closed_incidents: int


class TicketSummary(BaseModel):
    id: UUID
    incident_id: UUID
    lifecycle_status: str
    assigned_crew: str | None
    operator_note: str | None
    ai_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    incident_type: str
    status: str
    feeder_id: str | None
    dt_id: str | None
    upstream_pole_id: str | None
    downstream_pole_id: str | None
    latitude: float | None
    longitude: float | None
    pincode: str | None
    affected_poles: int
    confidence: float
    confidence_reasons: list[str] = []
    opened_at: datetime


class TicketListResponse(BaseModel):
    items: list[TicketSummary]


class TicketAssignRequest(BaseModel):
    crew: str


class TransformerEntry(BaseModel):
    id: str
    feeder_id: str
    capacity_kva: int
    households_served: int


class TransformerListResponse(BaseModel):
    items: list[TransformerEntry]
