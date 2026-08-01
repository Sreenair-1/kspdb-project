from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import Settings
from app.seed import RegistrySeeder
from app.schemas import IncidentSummary, RegistrySummary

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

    def _apply_migration(self, conn: psycopg.Connection, migration: Migration) -> None:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(migration.path.read_text(encoding="utf-8"))
                cur.execute(
                    "insert into schema_migrations (version) values (%s)",
                    (migration.version,),
                )
