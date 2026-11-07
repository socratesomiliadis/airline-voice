"""Flight search against live PostgreSQL inventory and fares."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from airline_api.core.auth import require_agent_key
from airline_api.modules.bookings.dependencies import BookingServiceDep
from airline_api.modules.bookings.schemas import (
    FlightInformationQuery,
    FlightInformationResult,
    FlightSearch,
    FlightSearchResult,
)

router = APIRouter(prefix="/flights", tags=["flights"], dependencies=[Depends(require_agent_key)])


@router.get("", response_model=FlightSearchResult)
async def search_flights(
    query: Annotated[FlightSearch, Query()], service: BookingServiceDep
) -> FlightSearchResult:
    return await service.search(query)


@router.get("/information", response_model=FlightInformationResult)
async def flight_information(
    query: Annotated[FlightInformationQuery, Query()], service: BookingServiceDep
) -> FlightInformationResult:
    return await service.flight_information(query)
