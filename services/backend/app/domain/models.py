from dataclasses import dataclass, field


@dataclass(frozen=True)
class TopologyPole:
    pole_id: str
    dt_id: str
    feeder_id: str
    latitude: float
    longitude: float
    pincode: str | None


@dataclass(frozen=True)
class TopologyEdge:
    feeder_id: str
    dt_id: str
    parent_pole_id: str | None
    child_pole_id: str
    source: str
    confidence: float


@dataclass(frozen=True)
class TransformerInfo:
    dt_id: str
    feeder_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class PoleObservation:
    pole_id: str
    state: str
    confidence: float = 1.0


@dataclass(frozen=True)
class LocalizedFault:
    incident_type: str
    feeder_id: str
    dt_id: str | None
    upstream_pole_id: str | None
    downstream_pole_id: str | None
    latitude: float
    longitude: float
    pincode: str | None
    affected_poles: int
    confidence: float
    confidence_reasons: list[str] = field(default_factory=list)
