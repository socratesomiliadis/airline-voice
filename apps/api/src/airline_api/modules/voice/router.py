"""ElevenLabs webhook tools: ordinary authenticated POST requests with typed bodies."""

from fastapi import APIRouter, Depends

from airline_api.core.auth import require_agent_key
from airline_api.core.placeholders import not_implemented
from airline_api.modules.bookings.dependencies import BookingServiceDep
from airline_api.modules.bookings.schemas import (
    AddBookingItems,
    AddBookingItemsTool,
    BookFlight,
    BookingReference,
    BookingView,
    CancelBooking,
    CancelBookingTool,
    FlightInformationQuery,
    FlightInformationResult,
    FlightSearch,
    FlightSearchResult,
    RescheduleBooking,
    RescheduleBookingTool,
)

router = APIRouter(prefix="/voice", tags=["voice"])
tools = APIRouter(prefix="/webhooks/elevenlabs", dependencies=[Depends(require_agent_key)])


@router.post("/sessions", status_code=501, response_model=None, summary="Create a voice session")
async def create_session() -> None:
    not_implemented("voice.create_session")


@tools.post("/search_flights", response_model=FlightSearchResult)
async def search_flights(request: FlightSearch, service: BookingServiceDep) -> FlightSearchResult:
    return await service.search(request)


@tools.post("/book_flight", response_model=BookingView)
async def book_flight(request: BookFlight, service: BookingServiceDep) -> BookingView:
    return await service.book(request)


@tools.post("/get_flight_information", response_model=FlightInformationResult)
async def get_flight_information(
    request: FlightInformationQuery, service: BookingServiceDep
) -> FlightInformationResult:
    return await service.flight_information(request)


@tools.post("/get_booking", response_model=BookingView)
async def get_booking(request: BookingReference, service: BookingServiceDep) -> BookingView:
    return await service.get(request.reference)


@tools.post("/cancel_booking", response_model=BookingView)
async def cancel_booking(request: CancelBookingTool, service: BookingServiceDep) -> BookingView:
    return await service.cancel(
        request.reference, CancelBooking.model_validate(request.model_dump(exclude={"reference"}))
    )


@tools.post("/reschedule_booking", response_model=BookingView)
async def reschedule_booking(
    request: RescheduleBookingTool, service: BookingServiceDep
) -> BookingView:
    return await service.reschedule(
        request.reference,
        RescheduleBooking.model_validate(request.model_dump(exclude={"reference"})),
    )


@tools.post("/add_booking_items", response_model=BookingView)
async def add_booking_items(
    request: AddBookingItemsTool, service: BookingServiceDep
) -> BookingView:
    return await service.add_items(
        request.reference, AddBookingItems.model_validate(request.model_dump(exclude={"reference"}))
    )


router.include_router(tools)
