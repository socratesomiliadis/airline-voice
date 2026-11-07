"""Validated REST and agent-tool inputs and JSON response contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

type SeatClass = Literal["economy", "premium_economy", "business"]
type FareTier = Literal["basic", "standard", "flexible", "business"]
type SeatPreference = Literal["window", "aisle", "extra_legroom"]
type Identifier = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
type Measurement = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FlightSearch(Input):
    destination: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        description="IATA code or city name, e.g. JFK or New York.",
    )
    origin: str | None = Field(default=None, min_length=2, max_length=80)
    departure_date: date | None = Field(
        default=None, description="Local departure date at the origin airport, YYYY-MM-DD."
    )
    departure_date_from: date | None = Field(
        default=None, description="Inclusive first local departure date, YYYY-MM-DD."
    )
    departure_date_to: date | None = Field(
        default=None, description="Inclusive last local departure date, YYYY-MM-DD."
    )
    min_price_cents: int | None = Field(
        default=None, ge=0, description="Minimum per-passenger fare in USD cents."
    )
    max_price_cents: int | None = Field(
        default=None, ge=0, description="Maximum per-passenger fare in USD cents."
    )
    seat_class: SeatClass | None = None
    fare_tier: FareTier | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    sort_by: Literal["departure", "price"] = "departure"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def price_bounds(self) -> Self:
        if self.departure_date is not None and (
            self.departure_date_from is not None or self.departure_date_to is not None
        ):
            raise ValueError("Use departure_date or a departure date range, not both")
        if (
            self.departure_date_from is not None
            and self.departure_date_to is not None
            and self.departure_date_from > self.departure_date_to
        ):
            raise ValueError("First departure date cannot exceed last departure date")
        if (
            self.min_price_cents is not None
            and self.max_price_cents is not None
            and self.min_price_cents > self.max_price_cents
        ):
            raise ValueError("Minimum price cannot exceed maximum price")
        return self


class Passenger(Input):
    passenger_id: Identifier = Field(
        description="Stable passenger ID. Reuse across calls and retries."
    )
    full_name: str = Field(min_length=2, max_length=160)
    seat_preference: SeatPreference | None = Field(
        default=None,
        description=(
            "Requested seating: window, aisle, or extra_legroom. Recorded as a request only; "
            "no seat assignment or extra-legroom price/availability is guaranteed."
        ),
    )

    @field_validator("passenger_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.casefold()


class Mutation(Input):
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        description="Unique action key. Reuse the exact key and request on retry.",
    )
    caller_id: Identifier = Field(
        description="Stable simulated caller or conversation ID for the audit history."
    )


class BookFlight(Mutation):
    flight_id: UUID
    seat_class: SeatClass
    fare_tier: FareTier
    expected_unit_price_cents: int = Field(
        gt=0,
        description="The per-passenger price returned by flight search; rejects a changed quote.",
    )
    passengers: list[Passenger] = Field(min_length=1, max_length=9)

    @model_validator(mode="after")
    def unique_passengers(self) -> Self:
        ids = [passenger.passenger_id for passenger in self.passengers]
        if len(ids) != len(set(ids)):
            raise ValueError("Passenger IDs must be unique within a booking")
        return self


class CancelBooking(Mutation):
    pass


class RescheduleBooking(Mutation):
    flight_id: UUID
    seat_class: SeatClass
    fare_tier: FareTier
    expected_unit_price_cents: int = Field(gt=0)


class ExtraItem(Input):
    passenger_id: Identifier
    item_type: Literal[
        "checked_bag",
        "stroller",
        "car_seat",
        "mobility_aid",
        "medical_device",
        "sports_equipment",
        "musical_instrument",
        "cabin_pet",
    ]
    weight_kg: Measurement | None = None
    length_cm: Measurement | None = None
    width_cm: Measurement | None = None
    height_cm: Measurement | None = None
    description: str = Field(default="", max_length=1000)

    @field_validator("passenger_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.casefold()

    @model_validator(mode="after")
    def bag_measurements(self) -> Self:
        if self.item_type == "checked_bag" and any(
            value is None
            for value in [self.weight_kg, self.length_cm, self.width_cm, self.height_cm]
        ):
            raise ValueError("Checked bags require weight_kg, length_cm, width_cm, and height_cm")
        return self


class AddBookingItems(Mutation):
    items: list[ExtraItem] = Field(
        min_length=1,
        max_length=20,
        description=(
            "New physical items to register. For checked bags, include unrecorded fare-included "
            "bags as well as paid bags; the backend applies the allowance once per passenger. "
            "Do not resubmit bags already present in the booking's confirmed extras."
        ),
    )


class BookingReference(Input):
    reference: str = Field(min_length=1, max_length=36)


class CancelBookingTool(CancelBooking, BookingReference):
    pass


class RescheduleBookingTool(RescheduleBooking, BookingReference):
    pass


class AddBookingItemsTool(AddBookingItems, BookingReference):
    pass


class FlightOffer(BaseModel):
    flight_id: UUID
    flight_number: str
    origin: str
    destination: str
    origin_city: str
    destination_city: str
    departure_at: datetime
    arrival_at: datetime
    departure_local: datetime
    arrival_local: datetime
    route_type: str
    seat_class: str
    fare_tier: str
    available_seats: int
    unit_price_cents: int
    total_price_cents: int
    currency: str
    checked_bags_per_passenger: int
    checked_bag_weight_limit_kg: int


class FlightSearchResult(BaseModel):
    offers: list[FlightOffer]
    limit: int
    offset: int
    has_more: bool


class FlightInformationQuery(Input):
    flight_number: str = Field(min_length=1, max_length=12)
    departure_date: date = Field(description="Local departure date at the origin airport.")


class FlightInformation(BaseModel):
    flight_id: UUID
    flight_number: str
    origin: str
    destination: str
    departure_local: datetime
    arrival_local: datetime
    origin_timezone: str
    destination_timezone: str
    status: Literal["scheduled", "cancelled", "departed", "arrived"]
    gate: str | None
    information_mode: Literal["fictional_database"] = "fictional_database"


class FlightInformationResult(BaseModel):
    flights: list[FlightInformation]


class PassengerView(Passenger):
    seat_preference_status: Literal["requested", "not_requested"] = "not_requested"


class ExtraView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    passenger_id: str
    item_type: str
    status: str
    weight_kg: Decimal | None
    length_cm: Decimal | None
    width_cm: Decimal | None
    height_cm: Decimal | None
    details: dict[str, Any]
    price_cents: int
    quoted_price_cents: int | None


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    caller_id: str
    charged_cents: int
    refunded_cents: int
    credit_cents: int
    details: dict[str, Any]
    created_at: datetime


class BookingView(BaseModel):
    id: UUID
    reference: str
    caller_id: str
    status: str
    flight: dict[str, Any]
    seat_class: str
    fare_tier: str
    passengers: list[PassengerView]
    unit_price_cents: int
    ticket_total_cents: int
    currency: str
    policy_version: str
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    extras: list[ExtraView]
    events: list[EventView]
    total_charged_cents: int
    total_refunded_cents: int
    total_credit_cents: int
    payment_mode: Literal["simulation"] = "simulation"
