"""Bookings, passenger allocations, extras, audit events, and durable retry receipts."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from airline_api.infrastructure.database.base import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_id", "seat_class", "fare_tier"],
            ["flight_fares.flight_id", "flight_fares.seat_class", "flight_fares.fare_tier"],
        ),
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="valid_status"),
        CheckConstraint(
            "passenger_count > 0 AND passenger_count <= 9", name="valid_passenger_count"
        ),
        CheckConstraint("unit_price_cents > 0", name="positive_unit_price"),
        CheckConstraint(
            "ticket_total_cents = unit_price_cents * passenger_count", name="ticket_total_matches"
        ),
        CheckConstraint("currency = 'USD'", name="supported_currency"),
        Index("ix_bookings_caller_created", "caller_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    reference: Mapped[str] = mapped_column(String(10), unique=True)
    caller_id: Mapped[str] = mapped_column(String(128))
    flight_id: Mapped[UUID] = mapped_column(Uuid)
    seat_class: Mapped[str] = mapped_column(String(24))
    fare_tier: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    passenger_count: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    ticket_total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    original_departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booked_departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booked_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(32))
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)


class BookingPassenger(Base):
    __tablename__ = "booking_passengers"

    booking_id: Mapped[UUID] = mapped_column(ForeignKey("bookings.id"), primary_key=True)
    passenger_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))


class PassengerReservation(Base):
    """Only active allocations live here; cancellation releases the unique passenger/flight pair."""

    __tablename__ = "passenger_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["booking_id", "passenger_id"],
            ["booking_passengers.booking_id", "booking_passengers.passenger_id"],
        ),
    )

    passenger_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    flight_id: Mapped[UUID] = mapped_column(ForeignKey("flights.id"), primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(Uuid, index=True)


class BookingExtra(Base):
    __tablename__ = "booking_extras"
    __table_args__ = (
        ForeignKeyConstraint(
            ["booking_id", "passenger_id"],
            ["booking_passengers.booking_id", "booking_passengers.passenger_id"],
        ),
        CheckConstraint(
            "status IN ('confirmed', 'pending_confirmation', 'cancelled')", name="valid_status"
        ),
        CheckConstraint("price_cents >= 0", name="nonnegative_price"),
        CheckConstraint(
            "quoted_price_cents IS NULL OR quoted_price_cents >= 0", name="nonnegative_quote"
        ),
        Index("ix_booking_extras_booking", "booking_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(Uuid)
    passenger_id: Mapped[str] = mapped_column(String(128))
    item_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    price_cents: Mapped[int] = mapped_column(Integer)
    quoted_price_cents: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BookingEvent(Base):
    __tablename__ = "booking_events"
    __table_args__ = (
        CheckConstraint(
            "charged_cents >= 0 AND refunded_cents >= 0 AND credit_cents >= 0",
            name="nonnegative_amounts",
        ),
        Index("ix_booking_events_booking_created", "booking_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("bookings.id"))
    action: Mapped[str] = mapped_column(String(24))
    caller_id: Mapped[str] = mapped_column(String(128))
    charged_cents: Mapped[int] = mapped_column(Integer)
    refunded_cents: Mapped[int] = mapped_column(Integer)
    credit_cents: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiOperation(Base):
    __tablename__ = "api_operations"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(200))
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
