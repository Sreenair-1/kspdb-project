from fastapi.testclient import TestClient

from app.dependencies import get_database
from app.detection import DetectionResult
from app.main import app


class FakeDatabase:
    def simulate_fault(self, **kwargs: object) -> tuple[int, int]:
        return 5, 5

    def simulate_repair(self, **kwargs: object) -> tuple[int, int]:
        return 5, 5

    def detect_faults(self) -> DetectionResult:
        return DetectionResult(new_incidents=1, closed_incidents=0, suppressed=0)


def _override() -> FakeDatabase:
    return FakeDatabase()


# ---------------------------------------------------------------------------
# Validation — 422 before any DB call
# ---------------------------------------------------------------------------


def test_span_fault_requires_downstream_pole_id() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post("/api/v1/simulate/fault", json={"fault_type": "span"})
    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "downstream_pole_id" in response.json()["detail"]


def test_dt_fault_requires_dt_id() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post("/api/v1/simulate/fault", json={"fault_type": "dt"})
    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "dt_id" in response.json()["detail"]


def test_feeder_fault_requires_feeder_id() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post("/api/v1/simulate/fault", json={"fault_type": "feeder"})
    app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "feeder_id" in response.json()["detail"]


def test_repair_requires_at_least_one_identifier() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post("/api/v1/simulate/repair", json={})
    app.dependency_overrides.clear()
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Happy path — response schema
# ---------------------------------------------------------------------------


def test_span_fault_returns_simulate_response() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/simulate/fault",
        json={"fault_type": "span", "downstream_pole_id": "P-000001"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["affected_poles"] == 5
    assert body["injected_events"] == 5
    assert body["new_incidents"] == 1
    assert body["closed_incidents"] == 0


def test_repair_returns_simulate_response() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/simulate/repair",
        json={"downstream_pole_id": "P-000001"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["affected_poles"] == 5
    assert body["injected_events"] == 5
    assert "new_incidents" in body
    assert "closed_incidents" in body
