"""Create airports, flight schedules, shared cabin inventory, and fares.

Revision ID: 0001_flight_inventory
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_flight_inventory"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "airports",
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "flights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flight_number", sa.String(12), nullable=False),
        sa.Column("airline", sa.String(80), nullable=False),
        sa.Column("origin_code", sa.String(3), nullable=False),
        sa.Column("destination_code", sa.String(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("route_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="scheduled", nullable=False),
        sa.CheckConstraint("origin_code <> destination_code", name="different_airports"),
        sa.CheckConstraint("arrival_at > departure_at", name="arrival_after_departure"),
        sa.CheckConstraint("route_type IN ('domestic', 'international')", name="valid_route_type"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'departed', 'arrived')", name="valid_status"
        ),
        sa.ForeignKeyConstraint(["origin_code"], ["airports.code"]),
        sa.ForeignKeyConstraint(["destination_code"], ["airports.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flight_number", "departure_at"),
    )
    op.create_index(
        "ix_flights_search", "flights", ["origin_code", "destination_code", "departure_at"]
    )
    op.create_table(
        "flight_cabins",
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("seat_class", sa.String(24), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("available_seats", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "seat_class IN ('economy', 'premium_economy', 'business')", name="valid_seat_class"
        ),
        sa.CheckConstraint("capacity > 0", name="positive_capacity"),
        sa.CheckConstraint(
            "available_seats >= 0 AND available_seats <= capacity", name="available_within_capacity"
        ),
        sa.ForeignKeyConstraint(["flight_id"], ["flights.id"]),
        sa.PrimaryKeyConstraint("flight_id", "seat_class"),
    )
    op.create_table(
        "flight_fares",
        sa.Column("flight_id", sa.Uuid(), nullable=False),
        sa.Column("seat_class", sa.String(24), nullable=False),
        sa.Column("fare_tier", sa.String(16), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.CheckConstraint("price_cents > 0", name="positive_price"),
        sa.CheckConstraint("currency = 'USD'", name="supported_currency"),
        sa.CheckConstraint(
            "(seat_class = 'economy' AND fare_tier IN ('basic', 'standard', 'flexible')) OR "
            "(seat_class = 'premium_economy' AND fare_tier IN ('standard', 'flexible')) OR "
            "(seat_class = 'business' AND fare_tier = 'business')",
            name="valid_fare_for_cabin",
        ),
        sa.ForeignKeyConstraint(
            ["flight_id", "seat_class"], ["flight_cabins.flight_id", "flight_cabins.seat_class"]
        ),
        sa.PrimaryKeyConstraint("flight_id", "seat_class", "fare_tier"),
    )


def downgrade() -> None:
    op.drop_table("flight_fares")
    op.drop_table("flight_cabins")
    op.drop_index("ix_flights_search", table_name="flights")
    op.drop_table("flights")
    op.drop_table("airports")
