from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import Database
from app.dependencies import get_database
from app.schemas import RegistrySummary, TransformerListResponse

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])


@router.get("/summary", response_model=RegistrySummary)
def registry_summary(db: Annotated[Database, Depends(get_database)]) -> RegistrySummary:
    return db.registry_summary()


@router.get("/transformers", response_model=TransformerListResponse)
def list_transformers(db: Annotated[Database, Depends(get_database)]) -> TransformerListResponse:
    return TransformerListResponse(items=db.list_transformers())
