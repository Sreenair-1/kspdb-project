"""
Regression tests for heartbeat-timeout downgrade.

Firmware 1.2 devices silently stop heartbeating on power loss.  After
_HEARTBEAT_TIMEOUT_MINUTES of silence a live pole must be treated as unknown
so the existing unknown-boundary localizer can report a fuzzy span fault.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.detection import _HEARTBEAT_TIMEOUT_MINUTES, _apply_heartbeat_timeout
from app.domain.models import PoleObservation

_NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
_THRESHOLD = _HEARTBEAT_TIMEOUT_MINUTES


def _row(
    pole_id: str = "P-001",
    state: str = "live",
    confidence: float = 1.0,
    last_heartbeat_at: datetime | None = None,
) -> dict:
    return {
        "pole_id": pole_id,
        "state": state,
        "confidence": confidence,
        "last_heartbeat_at": last_heartbeat_at,
    }


def test_stale_live_pole_becomes_unknown() -> None:
    """A live pole whose last heartbeat exceeds the timeout must become unknown."""
    rows = [_row(last_heartbeat_at=_NOW - timedelta(minutes=_THRESHOLD + 1))]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert len(result) == 1
    assert result[0].state == "unknown"


def test_recent_live_pole_stays_live() -> None:
    """A live pole whose last heartbeat is within the window must stay live."""
    rows = [_row(last_heartbeat_at=_NOW - timedelta(minutes=_THRESHOLD - 1))]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert result[0].state == "live"


def test_live_pole_with_null_heartbeat_stays_live() -> None:
    """A live pole that has never sent a heartbeat must not be downgraded."""
    rows = [_row(last_heartbeat_at=None)]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert result[0].state == "live"


def test_dark_pole_with_stale_heartbeat_stays_dark() -> None:
    """A confirmed dark pole must never be upgraded to unknown by the timeout."""
    rows = [
        _row(state="dark", confidence=0.95, last_heartbeat_at=_NOW - timedelta(hours=2))
    ]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert result[0].state == "dark"
    assert result[0].confidence == 0.95


def test_confidence_preserved_after_downgrade() -> None:
    """Observation confidence is not altered by the state downgrade."""
    rows = [_row(confidence=0.9, last_heartbeat_at=_NOW - timedelta(minutes=_THRESHOLD + 5))]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert result[0].state == "unknown"
    assert result[0].confidence == 0.9


def test_returns_pole_observation_instances() -> None:
    result = _apply_heartbeat_timeout(
        [_row(last_heartbeat_at=_NOW - timedelta(minutes=1))], _NOW
    )
    assert isinstance(result[0], PoleObservation)


def test_exactly_at_boundary_stays_live() -> None:
    """A pole whose last heartbeat is exactly at the cutoff must NOT be downgraded."""
    rows = [_row(last_heartbeat_at=_NOW - timedelta(minutes=_THRESHOLD))]
    result = _apply_heartbeat_timeout(rows, _NOW)
    assert result[0].state == "live"
