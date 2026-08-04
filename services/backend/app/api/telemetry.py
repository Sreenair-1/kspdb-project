from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import Database
from app.dependencies import get_database
from app.schemas import TelemetryEventRequest, TelemetryEventResponse

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryEventResponse, status_code=202)
def ingest_telemetry(
    event: TelemetryEventRequest,
    db: Annotated[Database, Depends(get_database)],
) -> TelemetryEventResponse:
    result = db.ingest_telemetry(
        device_id=event.device_id,
        pole_id=event.pole_id,
        event=event.event,
        energized=event.energized,
        device_ts=event.device_ts,
        seq=event.seq,
        battery_mv=event.battery_mv,
        rssi=event.rssi,
        firmware=event.firmware,
    )
    return TelemetryEventResponse(
        status="accepted",
        event_id=result.event_id,
        is_duplicate=result.is_duplicate,
        is_stale=result.is_stale,
    )
