from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg

from app.domain.localization import FaultLocalizer
from app.domain.models import (
    LocalizedFault,
    PoleObservation,
    TopologyEdge,
    TopologyPole,
    TransformerInfo,
)


@dataclass
class DetectionResult:
    new_incidents: int
    closed_incidents: int
    suppressed: int


def run_fault_detection(conn: psycopg.Connection) -> DetectionResult:
    transformers, poles, edges = _load_topology(conn)
    observations = _load_observations(conn)

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    open_incidents = _get_open_incidents(conn)
    open_set: dict[tuple, dict] = {_incident_key(i): i for i in open_incidents}

    active: list[LocalizedFault] = []
    suppressed = 0
    for fault in faults:
        if _is_scheduled_outage(conn, fault):
            suppressed += 1
        else:
            active.append(fault)

    fault_set: dict[tuple, LocalizedFault] = {_fault_key(f): f for f in active}

    new_keys = set(fault_set) - set(open_set)
    resolved_keys = set(open_set) - set(fault_set)

    new_incidents = 0
    for key in new_keys:
        _create_incident_and_ticket(conn, fault_set[key])
        new_incidents += 1

    closed_incidents = 0
    for key in resolved_keys:
        _close_incident(conn, open_set[key]["id"])
        closed_incidents += 1

    return DetectionResult(
        new_incidents=new_incidents,
        closed_incidents=closed_incidents,
        suppressed=suppressed,
    )


def _incident_key(incident: dict) -> tuple:
    return (
        incident["incident_type"],
        incident["feeder_id"],
        incident["dt_id"],
        incident["upstream_pole_id"],
        incident["downstream_pole_id"],
    )


def _fault_key(fault: LocalizedFault) -> tuple:
    return (
        fault.incident_type,
        fault.feeder_id,
        fault.dt_id,
        fault.upstream_pole_id,
        fault.downstream_pole_id,
    )


def _load_topology(
    conn: psycopg.Connection,
) -> tuple[list[TransformerInfo], list[TopologyPole], list[TopologyEdge]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, feeder_id, latitude, longitude FROM distribution_transformers"
        )
        transformers = [
            TransformerInfo(
                dt_id=row["id"],
                feeder_id=row["feeder_id"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            "SELECT id, dt_id, feeder_id, latitude, longitude, pincode FROM poles"
        )
        poles = [
            TopologyPole(
                pole_id=row["id"],
                dt_id=row["dt_id"],
                feeder_id=row["feeder_id"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                pincode=row["pincode"],
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT feeder_id, dt_id, parent_pole_id, child_pole_id, source, confidence
            FROM topology_edges
            """
        )
        edges = [
            TopologyEdge(
                feeder_id=row["feeder_id"],
                dt_id=row["dt_id"],
                parent_pole_id=row["parent_pole_id"],
                child_pole_id=row["child_pole_id"],
                source=row["source"],
                confidence=row["confidence"],
            )
            for row in cur.fetchall()
        ]

    return transformers, poles, edges


def _load_observations(conn: psycopg.Connection) -> list[PoleObservation]:
    with conn.cursor() as cur:
        cur.execute("SELECT pole_id, state, confidence FROM pole_states")
        return [
            PoleObservation(
                pole_id=row["pole_id"],
                state=row["state"],
                confidence=row["confidence"],
            )
            for row in cur.fetchall()
        ]


def _get_open_incidents(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, incident_type, feeder_id, dt_id, upstream_pole_id, downstream_pole_id
            FROM incidents
            WHERE status = 'detected'
            """
        )
        return cur.fetchall()


def _is_scheduled_outage(conn: psycopg.Connection, fault: LocalizedFault) -> bool:
    with conn.cursor() as cur:
        checks: list[tuple[str, str]] = []
        if fault.feeder_id:
            checks.append(("feeder", fault.feeder_id))
        if fault.dt_id:
            checks.append(("dt", fault.dt_id))
        for scope, target_id in checks:
            cur.execute(
                """
                SELECT 1 FROM scheduled_outages
                WHERE scope = %s AND target_id = %s
                  AND start_at <= now() AND end_at >= now()
                LIMIT 1
                """,
                (scope, target_id),
            )
            if cur.fetchone():
                return True
    return False


def _create_incident_and_ticket(conn: psycopg.Connection, fault: LocalizedFault) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO incidents (
              incident_type, status, feeder_id, dt_id, upstream_pole_id,
              downstream_pole_id, latitude, longitude, pincode,
              affected_poles, confidence, confidence_reasons
            )
            VALUES (%s, 'detected', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                fault.incident_type,
                fault.feeder_id,
                fault.dt_id,
                fault.upstream_pole_id,
                fault.downstream_pole_id,
                fault.latitude,
                fault.longitude,
                fault.pincode,
                fault.affected_poles,
                fault.confidence,
                json.dumps(fault.confidence_reasons),
            ),
        )
        incident_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO tickets (incident_id, lifecycle_status) VALUES (%s, 'detected')",
            (incident_id,),
        )


def _close_incident(conn: psycopg.Connection, incident_id: object) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE incidents SET status = 'closed', closed_at = now() WHERE id = %s",
            (incident_id,),
        )
        # Auto-verify the ticket — telemetry confirmed the fault is gone.
        cur.execute(
            """
            UPDATE tickets
            SET lifecycle_status = 'verified', verified_at = now(), updated_at = now()
            WHERE incident_id = %s
            """,
            (incident_id,),
        )
