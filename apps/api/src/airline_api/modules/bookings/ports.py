"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol
from uuid import UUID

from airline_contracts.types import JsonObject


class BookingService(Protocol):
    async def book(self, request: JsonObject) -> JsonObject: ...

    async def cancel(self, booking_id: UUID, request: JsonObject) -> JsonObject: ...

    async def reschedule(self, booking_id: UUID, request: JsonObject) -> JsonObject: ...


class BookingRepository(Protocol):
    async def get(self, booking_id: UUID) -> JsonObject | None: ...

    async def save(self, booking: JsonObject) -> None: ...
