from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.dependencies import get_database
from app.main import app
from app.schemas import TicketSummary

_TICKET_ID = UUID("22222222-2222-2222-2222-222222222222")
_INCIDENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_NOW = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)


def _make_ticket(lifecycle_status: str = "detected") -> TicketSummary:
    return TicketSummary(
        id=_TICKET_ID,
        incident_id=_INCIDENT_ID,
        lifecycle_status=lifecycle_status,
        assigned_crew=None,
        operator_note=None,
        created_at=_NOW,
        updated_at=_NOW,
        incident_type="span",
        status="detected",
        feeder_id="F-07-03",
        dt_id="D-0112",
        upstream_pole_id="P-000001",
        downstream_pole_id="P-000002",
        latitude=12.968214,
        longitude=77.594612,
        pincode="560078",
        affected_poles=5,
        confidence=0.92,
        opened_at=_NOW,
    )


class FakeDatabase:
    def __init__(self, resolve_ok: bool = True) -> None:
        self._resolve_ok = resolve_ok

    def list_tickets(self) -> list[TicketSummary]:
        return [_make_ticket()]

    def acknowledge_ticket(self, ticket_id: UUID) -> None:
        pass

    def assign_ticket(self, ticket_id: UUID, crew: str) -> None:
        pass

    def resolve_ticket(self, ticket_id: UUID) -> tuple[bool, str]:
        if self._resolve_ok:
            return True, "ok"
        return False, "3 pole(s) still reporting dark — cannot mark resolved"


def _override() -> FakeDatabase:
    return FakeDatabase()


def _override_pushback() -> FakeDatabase:
    return FakeDatabase(resolve_ok=False)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_tickets_returns_items_with_correct_schema() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.get("/api/v1/tickets")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["lifecycle_status"] == "detected"
    assert item["incident_type"] == "span"
    assert item["affected_poles"] == 5
    assert item["confidence"] == 0.92


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


def test_acknowledge_ticket_returns_200() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.patch(f"/api/v1/tickets/{_TICKET_ID}/acknowledge")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "lifecycle_status" in response.json()


def test_assign_ticket_returns_200_with_schema() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.patch(
        f"/api/v1/tickets/{_TICKET_ID}/assign",
        json={"crew": "Crew-Alpha"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert "lifecycle_status" in body
    assert "incident_type" in body


def test_resolve_ticket_returns_200_when_poles_live() -> None:
    app.dependency_overrides[get_database] = _override
    client = TestClient(app)
    response = client.patch(f"/api/v1/tickets/{_TICKET_ID}/resolve")
    app.dependency_overrides.clear()
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Resolve pushback
# ---------------------------------------------------------------------------


def test_resolve_ticket_returns_409_when_poles_still_dark() -> None:
    app.dependency_overrides[get_database] = _override_pushback
    client = TestClient(app)
    response = client.patch(f"/api/v1/tickets/{_TICKET_ID}/resolve")
    app.dependency_overrides.clear()
    assert response.status_code == 409
    assert "dark" in response.json()["detail"]
