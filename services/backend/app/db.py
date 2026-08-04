import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from app.config import Settings
from app.detection import DetectionResult, run_fault_detection
from app.schemas import IncidentSummary, RegistrySummary, TicketSummary, TransformerEntry
from app.seed import RegistrySeeder
from app.telemetry import TelemetryResult, process_telemetry_event

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path


class Database:
    def __init__(self, settings: Settings) -> None:
        self._database_url = settings.database_url

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def ping(self) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 as ok")
                row = cur.fetchone()
        return row is not None and row["ok"] == 1

    def run_migrations(self) -> None:
        with self.connect() as conn:
            self._ensure_migration_table(conn)
            applied = self._applied_versions(conn)
            for migration in self._available_migrations():
                if migration.version in applied:
                    continue
                self._apply_migration(conn, migration)

    def seed_registry_if_empty(self) -> bool:
        with self.connect() as conn:
            return RegistrySeeder().seed_if_empty(conn)

    def registry_summary(self) -> RegistrySummary:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      (select count(*) from feeders) as feeders,
                      (select count(*) from distribution_transformers) as transformers,
                      (select count(*) from poles) as poles,
                      (
                        select count(*) from poles where device_id is not null
                      ) as instrumented_poles,
                      (select count(*) from topology_edges where source = 'known') as known_edges,
                      (
                        select count(*) from topology_edges where source = 'inferred'
                      ) as inferred_edges
                    """
                )
                row = cur.fetchone()
        return RegistrySummary(**row)

    def list_transformers(self) -> list[TransformerEntry]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feeder_id, capacity_kva, households_served
                    FROM distribution_transformers
                    ORDER BY id
                    """
                )
                rows = cur.fetchall()
        return [TransformerEntry(**row) for row in rows]

    def list_incidents(self) -> list[IncidentSummary]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      id,
                      incident_type,
                      status,
                      feeder_id,
                      dt_id,
                      upstream_pole_id,
                      downstream_pole_id,
                      latitude,
                      longitude,
                      pincode,
                      affected_poles,
                      confidence,
                      opened_at
                    from incidents
                    order by opened_at desc
                    limit 100
                    """
                )
                rows = cur.fetchall()
        return [IncidentSummary(**row) for row in rows]

    def _ensure_migration_table(self, conn: psycopg.Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists schema_migrations (
                  version text primary key,
                  applied_at timestamptz not null default now()
                )
                """
            )
        conn.commit()

    def _applied_versions(self, conn: psycopg.Connection) -> set[str]:
        with conn.cursor() as cur:
            cur.execute("select version from schema_migrations")
            return {row["version"] for row in cur.fetchall()}

    def _available_migrations(self) -> Iterable[Migration]:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            yield Migration(version=path.stem, path=path)

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def ingest_telemetry(self, **kwargs: object) -> TelemetryResult:
        with self.connect() as conn:
            result = process_telemetry_event(conn, **kwargs)  # type: ignore[arg-type]
        if result.state_updated:
            with self.connect() as conn:
                run_fault_detection(conn)
        return result

    # ------------------------------------------------------------------
    # Fault detection (manual trigger)
    # ------------------------------------------------------------------

    def detect_faults(self) -> DetectionResult:
        with self.connect() as conn:
            return run_fault_detection(conn)

    # ------------------------------------------------------------------
    # Tickets
    # ------------------------------------------------------------------

    def list_tickets(self) -> list[TicketSummary]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      t.id, t.incident_id, t.lifecycle_status, t.assigned_crew,
                      t.operator_note, t.ai_summary, t.created_at, t.updated_at,
                      i.incident_type, i.status, i.feeder_id, i.dt_id,
                      i.upstream_pole_id, i.downstream_pole_id,
                      i.latitude, i.longitude, i.pincode,
                      i.affected_poles, i.confidence, i.confidence_reasons, i.opened_at
                    FROM tickets t
                    JOIN incidents i ON i.id = t.incident_id
                    ORDER BY t.created_at DESC
                    LIMIT 200
                    """
                )
                rows = cur.fetchall()
        return [TicketSummary(**row) for row in rows]

    def acknowledge_ticket(self, ticket_id: UUID) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET lifecycle_status = 'acknowledged', updated_at = now()
                    WHERE id = %s AND lifecycle_status = 'detected'
                    """,
                    (ticket_id,),
                )

    def assign_ticket(self, ticket_id: UUID, crew: str) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET lifecycle_status = 'crew_assigned', assigned_crew = %s, updated_at = now()
                    WHERE id = %s AND lifecycle_status IN ('detected', 'acknowledged')
                    """,
                    (crew, ticket_id),
                )

    def resolve_ticket(self, ticket_id: UUID) -> tuple[bool, str]:
        """Returns (success, reason). Fails if any in-scope pole is still dark."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.incident_type, i.dt_id, i.feeder_id, i.downstream_pole_id
                    FROM tickets t
                    JOIN incidents i ON i.id = t.incident_id
                    WHERE t.id = %s
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False, "Ticket not found"

                itype = row["incident_type"]
                dark_count = 0

                if itype == "span" and row["downstream_pole_id"]:
                    cur.execute(
                        "SELECT state FROM pole_states WHERE pole_id = %s",
                        (row["downstream_pole_id"],),
                    )
                    ps = cur.fetchone()
                    if ps and ps["state"] == "dark":
                        dark_count = 1
                elif itype == "dt" and row["dt_id"]:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM pole_states ps
                        JOIN poles p ON p.id = ps.pole_id
                        WHERE p.dt_id = %s AND ps.state = 'dark'
                        """,
                        (row["dt_id"],),
                    )
                    dark_count = cur.fetchone()["n"]
                elif itype == "feeder" and row["feeder_id"]:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM pole_states ps
                        JOIN poles p ON p.id = ps.pole_id
                        WHERE p.feeder_id = %s AND ps.state = 'dark'
                        """,
                        (row["feeder_id"],),
                    )
                    dark_count = cur.fetchone()["n"]

                if dark_count > 0:
                    return (
                        False,
                        f"{dark_count} pole(s) still reporting dark — cannot mark resolved",
                    )

                cur.execute(
                    """
                    UPDATE tickets
                    SET lifecycle_status = 'resolved',
                        resolved_marked_at = now(),
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (ticket_id,),
                )
        return True, "ok"

    # ------------------------------------------------------------------
    # Simulator helpers
    # ------------------------------------------------------------------

    def simulate_fault(
        self,
        *,
        fault_type: str,
        upstream_pole_id: str | None = None,
        downstream_pole_id: str | None = None,
        dt_id: str | None = None,
        feeder_id: str | None = None,
    ) -> tuple[int, int]:
        """Inject power_lost. Returns (affected_poles, injected_events)."""
        poles = self._fault_scope_poles(
            fault_type=fault_type,
            downstream_pole_id=downstream_pole_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
        )
        if not poles:
            return 0, 0
        injected = self._inject_events(poles, "power_lost", energized=False)
        return len(poles), injected

    def simulate_repair(
        self,
        *,
        downstream_pole_id: str | None = None,
        dt_id: str | None = None,
        feeder_id: str | None = None,
    ) -> tuple[int, int]:
        """Inject power_restored. Returns (affected_poles, injected_events)."""
        if downstream_pole_id:
            fault_type = "span"
        elif feeder_id:
            fault_type = "feeder"
        else:
            fault_type = "dt"
        poles = self._fault_scope_poles(
            fault_type=fault_type,
            downstream_pole_id=downstream_pole_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
        )
        if not poles:
            return 0, 0
        injected = self._inject_events(poles, "power_restored", energized=True)
        return len(poles), injected

    def _fault_scope_poles(
        self,
        *,
        fault_type: str,
        downstream_pole_id: str | None,
        dt_id: str | None,
        feeder_id: str | None,
    ) -> list[dict]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                if fault_type == "span" and downstream_pole_id:
                    cur.execute("SELECT dt_id FROM poles WHERE id = %s", (downstream_pole_id,))
                    row = cur.fetchone()
                    if not row:
                        return []
                    scope_dt = row["dt_id"]
                    cur.execute(
                        """
                        WITH RECURSIVE tree(pole_id) AS (
                          SELECT %s::text
                          UNION ALL
                          SELECT te.child_pole_id
                          FROM topology_edges te
                          JOIN tree t ON te.parent_pole_id = t.pole_id
                          WHERE te.dt_id = %s
                        )
                        SELECT p.id, p.device_id FROM poles p JOIN tree t ON p.id = t.pole_id
                        """,
                        (downstream_pole_id, scope_dt),
                    )
                elif fault_type == "dt" and dt_id:
                    cur.execute(
                        "SELECT id, device_id FROM poles WHERE dt_id = %s",
                        (dt_id,),
                    )
                elif fault_type == "feeder" and feeder_id:
                    cur.execute(
                        "SELECT id, device_id FROM poles WHERE feeder_id = %s",
                        (feeder_id,),
                    )
                else:
                    return []
                return cur.fetchall()

    def _inject_events(
        self,
        poles: list[dict],
        event: str,
        energized: bool,
    ) -> int:
        new_state = "dark" if not energized else "live"
        seq_base = int(time.time() * 1000) % (2_000_000_000)
        injected = 0

        with self.connect() as conn:
            with conn.cursor() as cur:
                # Update pole_states for ALL affected poles (including those without devices).
                cur.executemany(
                    """
                    INSERT INTO pole_states (pole_id, state, confidence)
                    VALUES (%s, %s, 0.95)
                    ON CONFLICT (pole_id) DO UPDATE SET
                      state = EXCLUDED.state,
                      confidence = EXCLUDED.confidence,
                      last_event_at = now(),
                      updated_at = now()
                    """,
                    [(p["id"], new_state) for p in poles],
                )

                # Insert telemetry events only for device-equipped poles.
                for offset, pole in enumerate(poles):
                    if not pole["device_id"]:
                        continue
                    seq = seq_base + offset
                    cur.execute(
                        """
                        INSERT INTO telemetry_events (
                          device_id, pole_id, event, energized, device_ts, seq,
                          battery_mv, rssi, firmware
                        )
                        VALUES (%s, %s, %s, %s, now(), %s, 3800, -75, 'sim-1.0')
                        ON CONFLICT (device_id, seq, event, energized, device_ts) DO NOTHING
                        """,
                        (pole["device_id"], pole["id"], event, energized, seq),
                    )
                    injected += 1

        return injected

    # ------------------------------------------------------------------
    # Internal migration helpers
    # ------------------------------------------------------------------

    def _apply_migration(self, conn: psycopg.Connection, migration: Migration) -> None:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(migration.path.read_text(encoding="utf-8"))
                cur.execute(
                    "insert into schema_migrations (version) values (%s)",
                    (migration.version,),
                )
