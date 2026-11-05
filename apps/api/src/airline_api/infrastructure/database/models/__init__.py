"""Register persistence models for Alembic discovery and application imports."""

from airline_api.infrastructure.database.models.bookings import (
    ApiOperation,
    Booking,
    BookingEvent,
    BookingExtra,
    BookingPassenger,
    PassengerReservation,
)
from airline_api.infrastructure.database.models.flights import (
    Airport,
    Flight,
    FlightCabin,
    FlightFare,
)

__all__ = [
    "Airport",
    "ApiOperation",
    "Booking",
    "BookingEvent",
    "BookingExtra",
    "BookingPassenger",
    "Flight",
    "FlightCabin",
    "FlightFare",
    "PassengerReservation",
]
