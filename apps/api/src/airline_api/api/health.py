"""Liveness and independent authenticated database readiness."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from airline_api.api.dependencies import get_session
from airline_api.core.auth import require_agent_key
from airline_api.infrastructure.database.models import Flight, FlightCabin, FlightFare

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    mode: Literal["simulation"] = "simulation"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", dependencies=[Depends(require_agent_key)])
async def ready(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict[str, str]:
    # Deliberately bypass BookingService.search, which may itself need repair.
    try:
        seeded = await session.scalar(
            select(Flight.id)
            .join(FlightCabin, FlightCabin.flight_id == Flight.id)
            .join(FlightFare, FlightFare.flight_id == Flight.id)
            .limit(1)
        )
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable or migrations missing") from None
    if seeded is None:
        raise HTTPException(503, "Seeded inventory required")
    now = request.app.state.settings.simulation_now or datetime.now(UTC)
    return {"status": "ok", "business_time": now.isoformat()}
