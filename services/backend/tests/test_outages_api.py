from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.dependencies import get_database
from app.main import app
from app.schemas import ScheduledOutageCreate, ScheduledOutageSummary


class FakeDatabase:
    def create_scheduled_outage(self, req: ScheduledOutageCreate) -> ScheduledOutageSummary:
        return ScheduledOutageSummary(
            id="test-id-1",
            scope=req.scope,
            target_id=req.target_id,
            start_at=req.start_at,
            end_at=req.end_at,
            reason=req.reason,
            created_at=datetime(2026, 8, 4, 10, 0, 0, tzinfo=UTC),
        )

    def list_scheduled_outages(self, *, active_only: bool = True) -> list[ScheduledOutageSummary]:
        return [
            ScheduledOutageSummary(
                id="test-id-1",
                scope="dt",
                target_id="DT-0001",
                start_at=datetime(2026, 8, 4, 9, 0, 0, tzinfo=UTC),
                end_at=datetime(2026, 8, 4, 11, 0, 0, tzinfo=UTC),
                reason="Maintenance",
                created_at=datetime(2026, 8, 4, 8, 0, 0, tzinfo=UTC),
            )
        ]


def _override() -> FakeDatabase:
    return FakeDatabase()


# ---------------------------------------------------------------------------
# Validation — 422 before any DB call
# ---------------------------------------------------------------------------


def test_invalid_scope_rejected() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/scheduled-outages",
        json={
            "scope": "pole",
            "target_id": "DT-0001",
            "start_at": "2026-08-04T09:00:00Z",
            "end_at": "2026-08-04T11:00:00Z",
            "reason": "Test",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_end_before_start_rejected() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/scheduled-outages",
        json={
            "scope": "dt",
            "target_id": "DT-0001",
            "start_at": "2026-08-04T11:00:00Z",
            "end_at": "2026-08-04T09:00:00Z",
            "reason": "Test",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_create_scheduled_outage_returns_201() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/scheduled-outages",
        json={
            "scope": "dt",
            "target_id": "DT-0001",
            "start_at": "2026-08-04T09:00:00Z",
            "end_at": "2026-08-04T11:00:00Z",
            "reason": "Scheduled maintenance",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["scope"] == "dt"
    assert body["target_id"] == "DT-0001"
    assert body["reason"] == "Scheduled maintenance"


def test_create_scheduled_outage_feeder_scope() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.post(
        "/api/v1/scheduled-outages",
        json={
            "scope": "feeder",
            "target_id": "FDR-01",
            "start_at": "2026-08-05T06:00:00Z",
            "end_at": "2026-08-05T10:00:00Z",
            "reason": "Cable replacement",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["scope"] == "feeder"


def test_list_scheduled_outages_returns_items() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.get("/api/v1/scheduled-outages")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["scope"] == "dt"
