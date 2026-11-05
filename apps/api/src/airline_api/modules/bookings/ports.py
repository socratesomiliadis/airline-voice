"""Typed application boundary shared by REST and agent tool adapters."""

from typing import Protocol

from airline_api.modules.bookings.schemas import (
    AddBookingItems,
    BookFlight,
    BookingView,
    CancelBooking,
    FlightSearch,
    FlightSearchResult,
    RescheduleBooking,
)


class BookingOperations(Protocol):
    async def search(self, query: FlightSearch) -> FlightSearchResult: ...

    async def get(self, reference: str) -> BookingView: ...

    async def list_bookings(
        self, limit: int = 50, offset: int = 0, caller_id: str | None = None
    ) -> list[BookingView]: ...

    async def book(self, request: BookFlight) -> BookingView: ...

    async def cancel(self, reference: str, request: CancelBooking) -> BookingView: ...

    async def reschedule(self, reference: str, request: RescheduleBooking) -> BookingView: ...

    async def add_items(self, reference: str, request: AddBookingItems) -> BookingView: ...
