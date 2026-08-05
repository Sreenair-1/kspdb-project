from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import Database
from app.dependencies import get_database
from app.schemas import (
    TicketAssignRequest,
    TicketListResponse,
    TicketsClearedResponse,
    TicketSummary,
)

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=TicketListResponse)
def list_tickets(db: Annotated[Database, Depends(get_database)]) -> TicketListResponse:
    return TicketListResponse(items=db.list_tickets())


@router.delete("", response_model=TicketsClearedResponse)
def clear_tickets(db: Annotated[Database, Depends(get_database)]) -> TicketsClearedResponse:
    tickets_deleted, incidents_deleted = db.clear_tickets()
    return TicketsClearedResponse(
        tickets_deleted=tickets_deleted, incidents_deleted=incidents_deleted
    )


@router.patch("/{ticket_id}/acknowledge", response_model=TicketSummary)
def acknowledge_ticket(
    ticket_id: UUID,
    db: Annotated[Database, Depends(get_database)],
) -> TicketSummary:
    db.acknowledge_ticket(ticket_id)
    return _get_or_404(db, ticket_id)


@router.patch("/{ticket_id}/assign", response_model=TicketSummary)
def assign_ticket(
    ticket_id: UUID,
    body: TicketAssignRequest,
    db: Annotated[Database, Depends(get_database)],
) -> TicketSummary:
    db.assign_ticket(ticket_id, body.crew)
    return _get_or_404(db, ticket_id)


@router.patch("/{ticket_id}/resolve", response_model=TicketSummary)
def resolve_ticket(
    ticket_id: UUID,
    db: Annotated[Database, Depends(get_database)],
) -> TicketSummary:
    ok, reason = db.resolve_ticket(ticket_id)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    return _get_or_404(db, ticket_id)


def _get_or_404(db: Database, ticket_id: UUID) -> TicketSummary:
    tickets = db.list_tickets()
    for t in tickets:
        if t.id == ticket_id:
            return t
    raise HTTPException(status_code=404, detail="Ticket not found")
