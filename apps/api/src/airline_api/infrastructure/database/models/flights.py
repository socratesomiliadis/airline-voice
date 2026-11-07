"""Persistent flight schedules, shared cabin inventory, and fare offers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from airline_api.infrastructure.database.base import Base


class Airport(Base):
    __tablename__ = "airports"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64))


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint("flight_number", "departure_at"),
        CheckConstraint("origin_code <> destination_code", name="different_airports"),
        CheckConstraint("arrival_at > departure_at", name="arrival_after_departure"),
        CheckConstraint("route_type IN ('domestic', 'international')", name="valid_route_type"),
        CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'departed', 'arrived')", name="valid_status"
        ),
        Index("ix_flights_search", "origin_code", "destination_code", "departure_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    flight_number: Mapped[str] = mapped_column(String(12))
    airline: Mapped[str] = mapped_column(String(80))
    origin_code: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    destination_code: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    route_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), server_default="scheduled")
    gate: Mapped[str | None] = mapped_column(String(16))


class FlightCabin(Base):
    __tablename__ = "flight_cabins"
    __table_args__ = (
        CheckConstraint(
            "seat_class IN ('economy', 'premium_economy', 'business')", name="valid_seat_class"
        ),
        CheckConstraint("capacity > 0", name="positive_capacity"),
        CheckConstraint(
            "available_seats >= 0 AND available_seats <= capacity", name="available_within_capacity"
        ),
    )

    flight_id: Mapped[UUID] = mapped_column(ForeignKey("flights.id"), primary_key=True)
    seat_class: Mapped[str] = mapped_column(String(24), primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer)
    available_seats: Mapped[int] = mapped_column(Integer)


class FlightFare(Base):
    __tablename__ = "flight_fares"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_id", "seat_class"], ["flight_cabins.flight_id", "flight_cabins.seat_class"]
        ),
        CheckConstraint("price_cents > 0", name="positive_price"),
        CheckConstraint("currency = 'USD'", name="supported_currency"),
        CheckConstraint(
            "(seat_class = 'economy' AND fare_tier IN ('basic', 'standard', 'flexible')) OR "
            "(seat_class = 'premium_economy' AND fare_tier IN ('standard', 'flexible')) OR "
            "(seat_class = 'business' AND fare_tier = 'business')",
            name="valid_fare_for_cabin",
        ),
    )

    flight_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    seat_class: Mapped[str] = mapped_column(String(24), primary_key=True)
    fare_tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
