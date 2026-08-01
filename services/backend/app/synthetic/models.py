from dataclasses import dataclass


@dataclass(frozen=True)
class FeederSeed:
    id: str
    substation_id: str
    name: str


@dataclass(frozen=True)
class TransformerSeed:
    id: str
    feeder_id: str
    latitude: float
    longitude: float
    capacity_kva: int
    households_served: int


@dataclass(frozen=True)
class PoleSeed:
    id: str
    feeder_id: str
    dt_id: str
    latitude: float
    longitude: float
    seq_on_line: int | None
    parent_pole_id: str | None
    pole_type: str
    ward: str
    pincode: str | None
    device_id: str | None


@dataclass(frozen=True)
class TopologyEdgeSeed:
    feeder_id: str
    dt_id: str
    parent_pole_id: str | None
    child_pole_id: str
    source: str
    confidence: float
    distance_m: float


@dataclass(frozen=True)
class DeviceStateSeed:
    device_id: str
    pole_id: str
    status: str
    firmware: str
    last_rssi: int


@dataclass(frozen=True)
class SyntheticNetwork:
    feeders: list[FeederSeed]
    transformers: list[TransformerSeed]
    poles: list[PoleSeed]
    topology_edges: list[TopologyEdgeSeed]
    device_states: list[DeviceStateSeed]
