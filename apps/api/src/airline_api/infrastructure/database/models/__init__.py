"""Register persistence models for Alembic discovery and application imports."""

from airline_api.infrastructure.database.models.flights import (
    Airport,
    Flight,
    FlightCabin,
    FlightFare,
)

__all__ = ["Airport", "Flight", "FlightCabin", "FlightFare"]
