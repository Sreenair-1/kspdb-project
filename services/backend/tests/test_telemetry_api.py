from uuid import UUID

from fastapi.testclient import TestClient

from app.dependencies import get_database
from app.main import app
from app.telemetry import TelemetryResult

_EVENT_ID = UUID("33333333-3333-3333-3333-333333333333")

_PAYLOAD = {
    "device_id": "DEV-001",
    "pole_id": "P-000001",
    "event": "power_lost",
    "energized": False,
    "device_ts": "2026-08-01T10:00:00Z",
    "seq": 1001,
    "battery_mv": 3800,
    "rssi": -75,
    "firmware": "1.2.3",
}


class FakeDatabase:
    def __init__(self, result: TelemetryResult) -> None:
        self._result = result

    def ingest_telemetry(self, **kwargs: object) -> TelemetryResult:
        return self._result


def _override(result: TelemetryResult):  # type: ignore[no-untyped-def]
    def factory() -> FakeDatabase:
        return FakeDatabase(result)

    return factory


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_telemetry_accepted_returns_202() -> None:
    result = TelemetryResult(
        event_id=_EVENT_ID, is_duplicate=False, is_stale=False, state_updated=True
    )
    app.dependency_overrides[get_database] = _override(result)
    client = TestClient(app)
    response = client.post("/api/v1/telemetry", json=_PAYLOAD)
    app.dependency_overrides.clear()
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["event_id"] == str(_EVENT_ID)
    assert body["is_duplicate"] is False
    assert body["is_stale"] is False


def test_telemetry_duplicate_flag_is_propagated() -> None:
    result = TelemetryResult(
        event_id=_EVENT_ID, is_duplicate=True, is_stale=False, state_updated=False
    )
    app.dependency_overrides[get_database] = _override(result)
    client = TestClient(app)
    response = client.post("/api/v1/telemetry", json=_PAYLOAD)
    app.dependency_overrides.clear()
    assert response.status_code == 202
    body = response.json()
    assert body["is_duplicate"] is True
    assert body["status"] == "accepted"


def test_telemetry_stale_flag_is_propagated() -> None:
    result = TelemetryResult(
        event_id=_EVENT_ID, is_duplicate=False, is_stale=True, state_updated=False
    )
    app.dependency_overrides[get_database] = _override(result)
    client = TestClient(app)
    response = client.post("/api/v1/telemetry", json=_PAYLOAD)
    app.dependency_overrides.clear()
    assert response.status_code == 202
    body = response.json()
    assert body["is_stale"] is True
    assert body["is_duplicate"] is False


def test_telemetry_invalid_event_type_rejected() -> None:
    result = TelemetryResult(
        event_id=_EVENT_ID, is_duplicate=False, is_stale=False, state_updated=False
    )
    app.dependency_overrides[get_database] = _override(result)
    client = TestClient(app)
    bad_payload = {**_PAYLOAD, "event": "unknown_event"}
    response = client.post("/api/v1/telemetry", json=bad_payload)
    app.dependency_overrides.clear()
    assert response.status_code == 422
