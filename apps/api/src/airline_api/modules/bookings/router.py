"""Reserved bookings endpoints; no handlers perform work."""

from uuid import UUID

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("", status_code=501, response_model=None, summary="List bookings")
async def list_bookings() -> None:
    not_implemented("bookings.list_bookings")


@router.post("", status_code=501, response_model=None, summary="Create a booking")
async def create_booking() -> None:
    not_implemented("bookings.create_booking")


@router.post(
    "/{booking_id}/cancel", status_code=501, response_model=None, summary="Cancel a booking"
)
async def cancel_booking(booking_id: UUID) -> None:
    not_implemented("bookings.cancel_booking")


@router.post(
    "/{booking_id}/reschedule", status_code=501, response_model=None, summary="Reschedule a booking"
)
async def reschedule_booking(booking_id: UUID) -> None:
    not_implemented("bookings.reschedule_booking")
