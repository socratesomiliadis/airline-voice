"""Persist bookings passenger allocations extras and idempotency

Revision ID: 0002_bookings
Revises: 0001_flight_inventory
Create Date: 2026-11-05 12:11:32.105846
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_bookings"
down_revision: str | Sequence[str] | None = "0001_flight_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_operations",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=200), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("idempotency_key", name=op.f("pk_api_operations")),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(length=10), nullable=False),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("seat_class", sa.String(length=24), nullable=False),
        sa.Column("fare_tier", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("passenger_count", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("ticket_total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("original_departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("currency = 'USD'", name=op.f("ck_bookings_supported_currency")),
        sa.CheckConstraint(
            "status IN ('confirmed', 'cancelled')", name=op.f("ck_bookings_valid_status")
        ),
        sa.CheckConstraint(
            "passenger_count > 0 AND passenger_count <= 9",
            name=op.f("ck_bookings_valid_passenger_count"),
        ),
        sa.CheckConstraint(
            "ticket_total_cents = unit_price_cents * passenger_count",
            name=op.f("ck_bookings_ticket_total_matches"),
        ),
        sa.CheckConstraint("unit_price_cents > 0", name=op.f("ck_bookings_positive_unit_price")),
        sa.ForeignKeyConstraint(
            ["flight_id", "seat_class", "fare_tier"],
            ["flight_fares.flight_id", "flight_fares.seat_class", "flight_fares.fare_tier"],
            name=op.f("fk_bookings_flight_id_flight_fares"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.UniqueConstraint("reference", name=op.f("uq_bookings_reference")),
    )
    op.create_index(
        "ix_bookings_caller_created", "bookings", ["caller_id", "created_at"], unique=False
    )
    op.create_table(
        "booking_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("charged_cents", sa.Integer(), nullable=False),
        sa.Column("refunded_cents", sa.Integer(), nullable=False),
        sa.Column("credit_cents", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "charged_cents >= 0 AND refunded_cents >= 0 AND credit_cents >= 0",
            name=op.f("ck_booking_events_nonnegative_amounts"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_booking_events_booking_id_bookings")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_events")),
    )
    op.create_index(
        "ix_booking_events_booking_created",
        "booking_events",
        ["booking_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "booking_passengers",
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("passenger_id", sa.String(length=128), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_booking_passengers_booking_id_bookings")
        ),
        sa.PrimaryKeyConstraint("booking_id", "passenger_id", name=op.f("pk_booking_passengers")),
    )
    op.create_table(
        "booking_extras",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("passenger_id", sa.String(length=128), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("length_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("width_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("height_cm", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("quoted_price_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('confirmed', 'pending_confirmation', 'cancelled')",
            name=op.f("ck_booking_extras_valid_status"),
        ),
        sa.CheckConstraint("price_cents >= 0", name=op.f("ck_booking_extras_nonnegative_price")),
        sa.CheckConstraint(
            "quoted_price_cents IS NULL OR quoted_price_cents >= 0",
            name=op.f("ck_booking_extras_nonnegative_quote"),
        ),
        sa.ForeignKeyConstraint(
            ["booking_id", "passenger_id"],
            ["booking_passengers.booking_id", "booking_passengers.passenger_id"],
            name=op.f("fk_booking_extras_booking_id_booking_passengers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_extras")),
    )
    op.create_index("ix_booking_extras_booking", "booking_extras", ["booking_id"], unique=False)
    op.create_table(
        "passenger_reservations",
        sa.Column("passenger_id", sa.String(length=128), nullable=False),
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id", "passenger_id"],
            ["booking_passengers.booking_id", "booking_passengers.passenger_id"],
            name=op.f("fk_passenger_reservations_booking_id_booking_passengers"),
        ),
        sa.ForeignKeyConstraint(
            ["flight_id"], ["flights.id"], name=op.f("fk_passenger_reservations_flight_id_flights")
        ),
        sa.PrimaryKeyConstraint(
            "passenger_id", "flight_id", name=op.f("pk_passenger_reservations")
        ),
    )
    op.create_index(
        op.f("ix_passenger_reservations_booking_id"),
        "passenger_reservations",
        ["booking_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_passenger_reservations_booking_id"), table_name="passenger_reservations")
    op.drop_table("passenger_reservations")
    op.drop_index("ix_booking_extras_booking", table_name="booking_extras")
    op.drop_table("booking_extras")
    op.drop_table("booking_passengers")
    op.drop_index("ix_booking_events_booking_created", table_name="booking_events")
    op.drop_table("booking_events")
    op.drop_index("ix_bookings_caller_created", table_name="bookings")
    op.drop_table("bookings")
    op.drop_table("api_operations")
