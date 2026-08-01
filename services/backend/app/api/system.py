from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.db import Database
from app.dependencies import get_database
from app.schemas import HealthResponse, ReadinessResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service="backend", environment=settings.app_env)


@router.get("/ready", response_model=ReadinessResponse)
def ready(db: Annotated[Database, Depends(get_database)]) -> ReadinessResponse:
    return ReadinessResponse(status="ok", database=db.ping())
