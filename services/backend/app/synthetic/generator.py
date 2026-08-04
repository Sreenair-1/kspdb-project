from __future__ import annotations

import math
import random

from app.synthetic.models import (
    DeviceStateSeed,
    FeederSeed,
    PoleSeed,
    SyntheticNetwork,
    TopologyEdgeSeed,
    TransformerSeed,
)

BENGALURU_CENTER = (12.9716, 77.5946)
METERS_PER_DEGREE_LAT = 111_320
POLE_TYPES = ("LT-9m-PCC", "LT-8m-Steel", "LT-9m-RCC")
PIN_CODES = ("560078", "560070", "560004", "560011", "560041", "560082")


class SyntheticNetworkGenerator:
    def __init__(
        self,
        seed: int = 20260729,
        feeder_count: int = 31,
        transformer_count: int = 72,
        target_poles: int = 5_000,
    ) -> None:
        self._rng = random.Random(seed)
        self._feeder_count = feeder_count
        self._transformer_count = transformer_count
        self._target_poles = target_poles

    def generate(self) -> SyntheticNetwork:
        feeders = self._feeders()
        transformers = self._transformers(feeders)
        poles: list[PoleSeed] = []
        edges: list[TopologyEdgeSeed] = []
        devices: list[DeviceStateSeed] = []

        pole_counter = 1
        missing_topology_dts = set(self._missing_topology_dt_ids(transformers))
        pole_counts = self._pole_counts()

        for dt, pole_count in zip(transformers, pole_counts, strict=True):
            has_recorded_topology = dt.id not in missing_topology_dts
            dt_poles, dt_edges, dt_devices = self._dt_network(
                dt=dt,
                pole_count=pole_count,
                first_pole_number=pole_counter,
                has_recorded_topology=has_recorded_topology,
            )
            poles.extend(dt_poles)
            edges.extend(dt_edges)
            devices.extend(dt_devices)
            pole_counter += pole_count

        return SyntheticNetwork(
            feeders=feeders,
            transformers=transformers,
            poles=poles,
            topology_edges=edges,
            device_states=devices,
        )

    def _feeders(self) -> list[FeederSeed]:
        return [
            FeederSeed(
                id=f"F-07-{index:02d}",
                substation_id=f"SS-{1 + ((index - 1) % 4):02d}",
                name=f"Subdivision 07 Feeder {index:02d}",
            )
            for index in range(1, self._feeder_count + 1)
        ]

    def _transformers(self, feeders: list[FeederSeed]) -> list[TransformerSeed]:
        transformers: list[TransformerSeed] = []
        for index in range(1, self._transformer_count + 1):
            feeder = feeders[(index - 1) % len(feeders)]
            lat, lon = self._offset(
                BENGALURU_CENTER, self._rng.uniform(0, 3_500), self._rng.random()
            )
            capacity = self._rng.choice((100, 160, 250, 315, 500))
            households = max(25, int(capacity * self._rng.uniform(0.8, 1.6)))
            transformers.append(
                TransformerSeed(
                    id=f"D-{index:04d}",
                    feeder_id=feeder.id,
                    latitude=lat,
                    longitude=lon,
                    capacity_kva=capacity,
                    households_served=households,
                )
            )
        return transformers

    def _missing_topology_dt_ids(self, transformers: list[TransformerSeed]) -> list[str]:
        missing_count = round(len(transformers) * 0.60)
        return [dt.id for dt in self._rng.sample(transformers, missing_count)]

    def _pole_counts(self) -> list[int]:
        counts = [self._bounded_lognormal() for _ in range(self._transformer_count)]
        scale = self._target_poles / sum(counts)
        scaled = [min(240, max(9, round(count * scale))) for count in counts]

        while sum(scaled) != self._target_poles:
            delta = 1 if sum(scaled) < self._target_poles else -1
            candidates = [
                index
                for index, count in enumerate(scaled)
                if (delta > 0 and count < 240) or (delta < 0 and count > 9)
            ]
            if not candidates:
                break
            scaled[self._rng.choice(candidates)] += delta
        return scaled

    def _bounded_lognormal(self) -> int:
        return min(240, max(9, round(self._rng.lognormvariate(math.log(70), 0.45))))

    def _dt_network(
        self,
        dt: TransformerSeed,
        pole_count: int,
        first_pole_number: int,
        has_recorded_topology: bool,
    ) -> tuple[list[PoleSeed], list[TopologyEdgeSeed], list[DeviceStateSeed]]:
        pole_ids = [
            f"P-{number:06d}" for number in range(first_pole_number, first_pole_number + pole_count)
        ]
        parent_by_child = self._tree_parent_map(pole_ids)
        coordinate_by_pole = self._pole_coordinates(dt, pole_ids, parent_by_child)
        source = "known" if has_recorded_topology else "inferred"
        confidence = 0.98 if has_recorded_topology else 0.68

        poles = [
            self._pole_seed(
                dt=dt,
                pole_id=pole_id,
                sequence=index + 1,
                parent_id=parent_by_child[pole_id],
                coordinate=coordinate_by_pole[pole_id],
                has_recorded_topology=has_recorded_topology,
            )
            for index, pole_id in enumerate(pole_ids)
        ]
        edges = [
            TopologyEdgeSeed(
                feeder_id=dt.feeder_id,
                dt_id=dt.id,
                parent_pole_id=parent_by_child[pole_id],
                child_pole_id=pole_id,
                source=source,
                confidence=confidence,
                distance_m=self._edge_distance(
                    dt, pole_id, parent_by_child[pole_id], coordinate_by_pole
                ),
            )
            for pole_id in pole_ids
        ]
        devices = [self._device_state(pole) for pole in poles if pole.device_id is not None]
        return poles, edges, devices

    def _tree_parent_map(self, pole_ids: list[str]) -> dict[str, str | None]:
        parent_by_child: dict[str, str | None] = {pole_ids[0]: None}
        active_branch_tips = [pole_ids[0]]
        for index, pole_id in enumerate(pole_ids[1:], start=1):
            should_branch = index > 8 and len(active_branch_tips) < 5 and self._rng.random() < 0.07
            parent = (
                self._rng.choice(pole_ids[max(0, index - 12) : index])
                if should_branch
                else active_branch_tips[-1]
            )
            parent_by_child[pole_id] = parent
            if should_branch:
                active_branch_tips.append(pole_id)
            else:
                active_branch_tips[-1] = pole_id
        return parent_by_child

    def _pole_coordinates(
        self,
        dt: TransformerSeed,
        pole_ids: list[str],
        parent_by_child: dict[str, str | None],
    ) -> dict[str, tuple[float, float]]:
        coordinates: dict[str, tuple[float, float]] = {}
        heading_by_pole: dict[str, float] = {}
        base_heading = self._rng.random()

        for index, pole_id in enumerate(pole_ids):
            parent_id = parent_by_child[pole_id]
            parent_coordinate = (
                (dt.latitude, dt.longitude) if parent_id is None else coordinates[parent_id]
            )
            parent_heading = base_heading if parent_id is None else heading_by_pole[parent_id]
            branch_turn = self._rng.uniform(-0.18, 0.18)
            heading = (parent_heading + branch_turn + (0.18 if index % 23 == 0 else 0)) % 1
            distance_m = self._rng.uniform(24, 42)
            coordinates[pole_id] = self._offset(parent_coordinate, distance_m, heading)
            heading_by_pole[pole_id] = heading
        return coordinates

    def _pole_seed(
        self,
        dt: TransformerSeed,
        pole_id: str,
        sequence: int,
        parent_id: str | None,
        coordinate: tuple[float, float],
        has_recorded_topology: bool,
    ) -> PoleSeed:
        device_id = None
        if self._rng.random() < 0.91:
            device_id = f"KSPDB-SD07-{dt.id}-{pole_id.removeprefix('P-')}"
        return PoleSeed(
            id=pole_id,
            feeder_id=dt.feeder_id,
            dt_id=dt.id,
            latitude=coordinate[0],
            longitude=coordinate[1],
            seq_on_line=sequence if has_recorded_topology else None,
            parent_pole_id=parent_id if has_recorded_topology else None,
            pole_type=self._rng.choice(POLE_TYPES),
            ward=f"W-{self._rng.randint(70, 99):03d}",
            pincode=None if self._rng.random() < 0.03 else self._rng.choice(PIN_CODES),
            device_id=device_id,
        )

    def _device_state(self, pole: PoleSeed) -> DeviceStateSeed:
        firmware = "1.2.9" if self._rng.random() < 0.08 else self._rng.choice(("1.3.6", "1.4.2"))
        status = "offline" if self._rng.random() < 0.04 else "online"
        return DeviceStateSeed(
            device_id=pole.device_id or "",
            pole_id=pole.id,
            status=status,
            firmware=firmware,
            last_rssi=round(self._rng.uniform(-105, -68)),
        )

    def _edge_distance(
        self,
        dt: TransformerSeed,
        child_id: str,
        parent_id: str | None,
        coordinate_by_pole: dict[str, tuple[float, float]],
    ) -> float:
        parent_coordinate = (
            (dt.latitude, dt.longitude) if parent_id is None else coordinate_by_pole[parent_id]
        )
        child_coordinate = coordinate_by_pole[child_id]
        return round(self._distance_m(parent_coordinate, child_coordinate), 2)

    def _offset(
        self, origin: tuple[float, float], meters: float, heading_unit: float
    ) -> tuple[float, float]:
        angle = heading_unit * math.tau
        north_m = math.cos(angle) * meters
        east_m = math.sin(angle) * meters
        lat = origin[0] + north_m / METERS_PER_DEGREE_LAT
        lon = origin[1] + east_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(origin[0])))
        return round(lat, 6), round(lon, 6)

    def _distance_m(self, start: tuple[float, float], end: tuple[float, float]) -> float:
        lat_m = (end[0] - start[0]) * METERS_PER_DEGREE_LAT
        lon_m = (end[1] - start[1]) * METERS_PER_DEGREE_LAT * math.cos(math.radians(start[0]))
        return math.hypot(lat_m, lon_m)
