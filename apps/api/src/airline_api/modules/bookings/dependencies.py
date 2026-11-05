"""Compose the request-scoped application service for both transports."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from airline_api.api.dependencies import get_session
from airline_api.core.config import Settings
from airline_api.modules.bookings.policies import PolicyCatalog
from airline_api.modules.bookings.ports import BookingOperations
from airline_api.modules.bookings.service import BookingService


async def get_booking_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BookingOperations:
    policies: PolicyCatalog = request.app.state.policies
    settings: Settings = request.app.state.settings
    simulation_now = settings.simulation_now
    clock = (lambda: simulation_now) if simulation_now is not None else None
    return BookingService(session, policies, clock=clock)


type BookingServiceDep = Annotated[BookingOperations, Depends(get_booking_service)]
