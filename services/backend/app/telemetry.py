from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import psycopg


@dataclass
class TelemetryResult:
    event_id: UUID | None
    is_duplicate: bool
    is_stale: bool
    state_updated: bool


def process_telemetry_event(
    conn: psycopg.Connection,
    *,
    device_id: str,
    pole_id: str,
    event: str,
    energized: bool,
    device_ts: datetime,
    seq: int,
    battery_mv: int,
    rssi: int,
    firmware: str,
) -> TelemetryResult:
    with conn.cursor() as cur:
        # Staleness: reject if seq is not newer than what we have on record.
        cur.execute(
            "SELECT last_seq FROM device_states WHERE device_id = %s",
            (device_id,),
        )
        row = cur.fetchone()
        is_stale = bool(row and row["last_seq"] is not None and seq <= row["last_seq"])

        # Insert; unique constraint on (device_id, seq, event, energized, device_ts)
        # silently skips duplicates via DO NOTHING.
        cur.execute(
            """
            INSERT INTO telemetry_events (
              device_id, pole_id, event, energized, device_ts, seq,
              battery_mv, rssi, firmware, is_stale
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id, seq, event, energized, device_ts) DO NOTHING
            RETURNING id
            """,
            (device_id, pole_id, event, energized, device_ts, seq,
             battery_mv, rssi, firmware, is_stale),
        )
        row = cur.fetchone()
        if row is None:
            # Exact duplicate — look up the existing id for the response.
            cur.execute(
                """
                SELECT id FROM telemetry_events
                WHERE device_id = %s AND seq = %s AND event = %s
                  AND energized = %s AND device_ts = %s
                """,
                (device_id, seq, event, energized, device_ts),
            )
            existing = cur.fetchone()
            return TelemetryResult(
                event_id=existing["id"] if existing else None,
                is_duplicate=True,
                is_stale=is_stale,
                state_updated=False,
            )

        event_id: UUID = row["id"]

        if is_stale:
            return TelemetryResult(
                event_id=event_id,
                is_duplicate=False,
                is_stale=True,
                state_updated=False,
            )

        # Keep device_states current.
        cur.execute(
            """
            INSERT INTO device_states (
              device_id, pole_id, last_seq, status, firmware, last_rssi, last_seen_at
            )
            VALUES (%s, %s, %s, 'online', %s, %s, now())
            ON CONFLICT (device_id) DO UPDATE SET
              last_seq = EXCLUDED.last_seq,
              status = 'online',
              firmware = EXCLUDED.firmware,
              last_rssi = EXCLUDED.last_rssi,
              last_seen_at = now(),
              updated_at = now()
            """,
            (device_id, pole_id, seq, firmware, rssi),
        )

        if event == "power_lost" or (event == "heartbeat" and not energized):
            new_state = "dark"
            confidence = 0.95 if event == "power_lost" else 0.80
        else:
            new_state = "live"
            confidence = 1.0

        cur.execute(
            """
            INSERT INTO pole_states (pole_id, state, source_event_id, last_event_at, confidence)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (pole_id) DO UPDATE SET
              state = EXCLUDED.state,
              source_event_id = EXCLUDED.source_event_id,
              last_event_at = EXCLUDED.last_event_at,
              confidence = EXCLUDED.confidence,
              updated_at = now()
            """,
            (pole_id, new_state, event_id, device_ts, confidence),
        )

        if event == "heartbeat" and new_state == "live":
            cur.execute(
                "UPDATE pole_states SET last_heartbeat_at = %s WHERE pole_id = %s",
                (device_ts, pole_id),
            )

    return TelemetryResult(
        event_id=event_id,
        is_duplicate=False,
        is_stale=False,
        state_updated=True,
    )
