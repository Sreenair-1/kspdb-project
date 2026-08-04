from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import Database
from app.dependencies import get_database
from app.schemas import (
    ScheduledOutageCreate,
    ScheduledOutageListResponse,
    ScheduledOutageSummary,
)

router = APIRouter(prefix="/api/v1/scheduled-outages", tags=["scheduled-outages"])


@router.post("", response_model=ScheduledOutageSummary, status_code=201)
def create_scheduled_outage(
    req: ScheduledOutageCreate,
    db: Annotated[Database, Depends(get_database)],
) -> ScheduledOutageSummary:
    return db.create_scheduled_outage(req)


@router.get("", response_model=ScheduledOutageListResponse)
def list_scheduled_outages(
    db: Annotated[Database, Depends(get_database)],
    active_only: bool = True,
) -> ScheduledOutageListResponse:
    items = db.list_scheduled_outages(active_only=active_only)
    return ScheduledOutageListResponse(items=items)
