"""
Regression tests for boot-event seq-epoch handling.

A `boot` event must never be rejected as stale even when the incoming seq
(always 0 after reset) is ≤ the previously recorded last_seq.  After a boot
the seq_epoch counter in device_states must be incremented so that subsequent
events in the new epoch are not confused with delayed pre-boot messages.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

from app.telemetry import TelemetryResult, process_telemetry_event

_EVENT_ID = UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")
_NOW = datetime(2026, 8, 1, 10, 0, 0)

_BASE = dict(
    device_id="DEV-001",
    pole_id="P-000001",
    energized=True,
    device_ts=_NOW,
    battery_mv=3800,
    rssi=-75,
    firmware="1.4.2",
)


def _make_conn(*fetchone_returns: dict | None) -> MagicMock:
    """Return a mock psycopg Connection whose cursor yields the given fetchone values."""
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = list(fetchone_returns)

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_cur)
    ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = ctx
    return conn


def test_boot_event_not_stale_when_last_seq_is_high() -> None:
    """boot seq=0 must not be rejected even though last_seq=5000."""
    conn = _make_conn(
        {"last_seq": 5000},          # SELECT last_seq
        {"id": _EVENT_ID},           # INSERT telemetry_events RETURNING id
    )
    result: TelemetryResult = process_telemetry_event(
        conn, event="boot", seq=0, **_BASE
    )
    assert result.is_stale is False
    assert result.is_duplicate is False
    assert result.state_updated is True


def test_boot_event_not_stale_when_no_prior_record() -> None:
    """boot with no previous device_states row must also be accepted."""
    conn = _make_conn(
        None,            # SELECT last_seq → no row
        {"id": _EVENT_ID},
    )
    result = process_telemetry_event(conn, event="boot", seq=0, **_BASE)
    assert result.is_stale is False
    assert result.state_updated is True


def test_boot_event_increments_seq_epoch() -> None:
    """After a boot the INSERT/UPDATE must include seq_epoch increment."""
    conn = _make_conn(
        {"last_seq": 5000},
        {"id": _EVENT_ID},
    )
    mock_cur = conn.cursor.return_value.__enter__.return_value

    process_telemetry_event(conn, event="boot", seq=0, **_BASE)

    # Find the device_states execute call and verify it references seq_epoch.
    calls = [str(c) for c in mock_cur.execute.call_args_list]
    epoch_calls = [c for c in calls if "seq_epoch" in c]
    assert len(epoch_calls) >= 1, "Expected at least one SQL call referencing seq_epoch"


def test_non_boot_event_remains_stale_when_seq_too_low() -> None:
    """A regular heartbeat with seq ≤ last_seq must still be rejected as stale."""
    conn = _make_conn(
        {"last_seq": 5000},
        {"id": _EVENT_ID},
    )
    result = process_telemetry_event(
        conn, event="heartbeat", seq=100, **_BASE
    )
    assert result.is_stale is True
    assert result.state_updated is False
