from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db import Database
from app.dependencies import get_database
from app.schemas import SimulateFaultRequest, SimulateRepairRequest, SimulateResponse

router = APIRouter(prefix="/api/v1/simulate", tags=["simulate"])


@router.post("/fault", response_model=SimulateResponse)
def simulate_fault(
    request: SimulateFaultRequest,
    db: Annotated[Database, Depends(get_database)],
) -> SimulateResponse:
    _validate_fault_request(request)
    affected, injected = db.simulate_fault(
        fault_type=request.fault_type,
        upstream_pole_id=request.upstream_pole_id,
        downstream_pole_id=request.downstream_pole_id,
        dt_id=request.dt_id,
        feeder_id=request.feeder_id,
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="No poles found for the given scope")
    detection = db.detect_faults()
    return SimulateResponse(
        affected_poles=affected,
        injected_events=injected,
        new_incidents=detection.new_incidents,
        closed_incidents=detection.closed_incidents,
    )


@router.post("/repair", response_model=SimulateResponse)
def simulate_repair(
    request: SimulateRepairRequest,
    db: Annotated[Database, Depends(get_database)],
) -> SimulateResponse:
    if not any([request.downstream_pole_id, request.dt_id, request.feeder_id]):
        raise HTTPException(
            status_code=422,
            detail="Provide downstream_pole_id, dt_id, or feeder_id",
        )
    affected, injected = db.simulate_repair(
        downstream_pole_id=request.downstream_pole_id,
        dt_id=request.dt_id,
        feeder_id=request.feeder_id,
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="No poles found for the given scope")
    detection = db.detect_faults()
    return SimulateResponse(
        affected_poles=affected,
        injected_events=injected,
        new_incidents=detection.new_incidents,
        closed_incidents=detection.closed_incidents,
    )


def _validate_fault_request(request: SimulateFaultRequest) -> None:
    if request.fault_type == "span" and not request.downstream_pole_id:
        raise HTTPException(
            status_code=422,
            detail="downstream_pole_id required for span fault",
        )
    if request.fault_type == "dt" and not request.dt_id:
        raise HTTPException(
            status_code=422,
            detail="dt_id required for DT fault",
        )
    if request.fault_type == "feeder" and not request.feeder_id:
        raise HTTPException(
            status_code=422,
            detail="feeder_id required for feeder fault",
        )
