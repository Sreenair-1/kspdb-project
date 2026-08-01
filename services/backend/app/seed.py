from psycopg import Connection

from app.synthetic.generator import SyntheticNetworkGenerator
from app.synthetic.models import SyntheticNetwork


class RegistrySeeder:
    def __init__(self, generator: SyntheticNetworkGenerator | None = None) -> None:
        self._generator = generator or SyntheticNetworkGenerator()

    def seed_if_empty(self, conn: Connection) -> bool:
        with conn.cursor() as cur:
            cur.execute("select count(*) as count from feeders")
            if cur.fetchone()["count"] > 0:
                return False

        network = self._generator.generate()
        self._insert_network(conn, network)
        return True

    def _insert_network(self, conn: Connection, network: SyntheticNetwork) -> None:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    insert into feeders (id, substation_id, name)
                    values (%s, %s, %s)
                    """,
                    [(row.id, row.substation_id, row.name) for row in network.feeders],
                )
                cur.executemany(
                    """
                    insert into distribution_transformers (
                      id, feeder_id, latitude, longitude, capacity_kva, households_served
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            row.id,
                            row.feeder_id,
                            row.latitude,
                            row.longitude,
                            row.capacity_kva,
                            row.households_served,
                        )
                        for row in network.transformers
                    ],
                )
                cur.executemany(
                    """
                    insert into poles (
                      id, feeder_id, dt_id, latitude, longitude, seq_on_line,
                      parent_pole_id, pole_type, ward, pincode, device_id
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            row.id,
                            row.feeder_id,
                            row.dt_id,
                            row.latitude,
                            row.longitude,
                            row.seq_on_line,
                            row.parent_pole_id,
                            row.pole_type,
                            row.ward,
                            row.pincode,
                            row.device_id,
                        )
                        for row in network.poles
                    ],
                )
                cur.executemany(
                    """
                    insert into topology_edges (
                      feeder_id, dt_id, parent_pole_id, child_pole_id,
                      source, confidence, distance_m
                    )
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            row.feeder_id,
                            row.dt_id,
                            row.parent_pole_id,
                            row.child_pole_id,
                            row.source,
                            row.confidence,
                            row.distance_m,
                        )
                        for row in network.topology_edges
                    ],
                )
                cur.executemany(
                    """
                    insert into pole_states (pole_id, state, confidence)
                    values (%s, 'live', 1.0)
                    """,
                    [(row.id,) for row in network.poles],
                )
                cur.executemany(
                    """
                    insert into device_states (
                      device_id, pole_id, status, firmware, last_rssi, last_seen_at
                    )
                    values (%s, %s, %s, %s, %s, now())
                    """,
                    [
                        (
                            row.device_id,
                            row.pole_id,
                            row.status,
                            row.firmware,
                            row.last_rssi,
                        )
                        for row in network.device_states
                    ],
                )
