from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.dependencies import get_database
from app.main import app
from app.schemas import IncidentSummary, RegistrySummary


class FakeDatabase:
    def ping(self) -> bool:
        return True

    def registry_summary(self) -> RegistrySummary:
        return RegistrySummary(
            feeders=31,
            transformers=412,
            poles=38400,
            instrumented_poles=34900,
            known_edges=12000,
            inferred_edges=18000,
        )

    def list_incidents(self) -> list[IncidentSummary]:
        return [
            IncidentSummary(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                incident_type="span",
                status="detected",
                feeder_id="F-07-03",
                dt_id="D-0112",
                upstream_pole_id="P-024431",
                downstream_pole_id="P-024432",
                latitude=12.968214,
                longitude=77.594612,
                pincode="560078",
                affected_poles=17,
                confidence=0.92,
                opened_at=datetime(2026, 7, 29, 2, 14, 7, tzinfo=UTC),
            )
        ]


def override_database() -> FakeDatabase:
    return FakeDatabase()


def test_readiness_returns_database_status() -> None:
    app.dependency_overrides[get_database] = override_database
    client = TestClient(app)

    response = client.get("/ready")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True}


def test_registry_summary_contract() -> None:
    app.dependency_overrides[get_database] = override_database
    client = TestClient(app)

    response = client.get("/api/v1/registry/summary")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["poles"] == 38400
    assert response.json()["inferred_edges"] == 18000


def test_incident_list_contract() -> None:
    app.dependency_overrides[get_database] = override_database
    client = TestClient(app)

    response = client.get("/api/v1/incidents")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["incident_type"] == "span"
    assert body["items"][0]["affected_poles"] == 17
