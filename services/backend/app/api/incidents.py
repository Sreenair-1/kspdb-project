from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import Database
from app.dependencies import get_database
from app.schemas import IncidentListResponse

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=IncidentListResponse)
def list_incidents(db: Annotated[Database, Depends(get_database)]) -> IncidentListResponse:
    return IncidentListResponse(items=db.list_incidents())
