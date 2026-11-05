"""Persistent booking HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from airline_api.core.auth import require_agent_key
from airline_api.modules.bookings.dependencies import BookingServiceDep
from airline_api.modules.bookings.schemas import (
    AddBookingItems,
    BookFlight,
    BookingView,
    CancelBooking,
    RescheduleBooking,
)

router = APIRouter(prefix="/bookings", tags=["bookings"], dependencies=[Depends(require_agent_key)])
type BookingLocator = Annotated[str, Path(min_length=1, max_length=36)]


@router.get("", response_model=list[BookingView])
async def list_bookings(
    service: BookingServiceDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    caller_id: str | None = Query(None, max_length=128),
) -> list[BookingView]:
    return await service.list_bookings(limit, offset, caller_id)


@router.post("", response_model=BookingView, status_code=201)
async def create_booking(request: BookFlight, service: BookingServiceDep) -> BookingView:
    return await service.book(request)


@router.get("/{reference}", response_model=BookingView)
async def retrieve_booking(reference: BookingLocator, service: BookingServiceDep) -> BookingView:
    return await service.get(reference)


@router.post("/{reference}/cancel", response_model=BookingView)
async def cancel_booking(
    reference: BookingLocator, request: CancelBooking, service: BookingServiceDep
) -> BookingView:
    return await service.cancel(reference, request)


@router.post("/{reference}/reschedule", response_model=BookingView)
async def reschedule_booking(
    reference: BookingLocator, request: RescheduleBooking, service: BookingServiceDep
) -> BookingView:
    return await service.reschedule(reference, request)


@router.post("/{reference}/items", response_model=BookingView)
async def add_booking_items(
    reference: BookingLocator, request: AddBookingItems, service: BookingServiceDep
) -> BookingView:
    return await service.add_items(reference, request)
