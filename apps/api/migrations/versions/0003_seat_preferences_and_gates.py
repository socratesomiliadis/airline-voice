"""Persist passenger seat requests and fictional departure gates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_seat_preferences_and_gates"
down_revision: str | Sequence[str] | None = "0002_bookings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("booking_passengers", sa.Column("seat_preference", sa.String(16), nullable=True))
    op.create_check_constraint(
        "valid_seat_preference",
        "booking_passengers",
        "seat_preference IS NULL OR seat_preference IN ('window', 'aisle', 'extra_legroom')",
    )
    op.add_column("flights", sa.Column("gate", sa.String(16), nullable=True))
    # Existing fictional records receive the same gates as a fresh dataset import.
    op.execute(
        "UPDATE flights SET gate = 'A' || "
        "((substring(flight_number from '[0-9]+')::integer % 20) + 1)::text "
        "WHERE flight_number ~ '^DEMO[0-9]{3}$'"
    )


def downgrade() -> None:
    op.drop_column("flights", "gate")
    op.drop_constraint("valid_seat_preference", "booking_passengers", type_="check")
    op.drop_column("booking_passengers", "seat_preference")
