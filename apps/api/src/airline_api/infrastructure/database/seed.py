"""Validate and import fictional flight data without overwriting live inventory."""

import argparse
import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from airline_api.core.config import Settings
from airline_api.infrastructure.database.base import Base
from airline_api.infrastructure.database.models import Airport, Flight, FlightCabin, FlightFare

DEFAULT_DATASET = Path("data/flights/week_2026_11_09.json")
type SeatClass = Literal["economy", "premium_economy", "business"]
type FareTier = Literal["basic", "standard", "flexible", "business"]

FARE_TIERS_BY_CABIN: dict[str, set[str]] = {
    "economy": {"basic", "standard", "flexible"},
    "premium_economy": {"standard", "flexible"},
    "business": {"business"},
}


class SeedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AirportSeed(SeedRecord):
    code: str = Field(pattern=r"^[A-Z]{3}$")
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    timezone: str = Field(min_length=1, max_length=64)


class FareSeed(SeedRecord):
    fare_tier: FareTier
    price_cents: int = Field(strict=True, gt=0)


class CabinSeed(SeedRecord):
    seat_class: SeatClass
    capacity: int = Field(strict=True, gt=0)
    available_seats: int = Field(strict=True, ge=0)
    fares: list[FareSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_inventory_and_tiers(self) -> Self:
        if self.available_seats > self.capacity:
            raise ValueError("Available seats cannot exceed cabin capacity")
        tiers = [fare.fare_tier for fare in self.fares]
        if len(tiers) != len(set(tiers)) or set(tiers) != FARE_TIERS_BY_CABIN[self.seat_class]:
            raise ValueError("Fare tiers must be unique and match the cabin's supported tiers")
        return self


class FlightSeed(SeedRecord):
    id: UUID
    flight_number: str = Field(pattern=r"^DEMO[0-9]{3}$")
    origin_code: str = Field(pattern=r"^[A-Z]{3}$")
    destination_code: str = Field(pattern=r"^[A-Z]{3}$")
    departure_at: AwareDatetime
    arrival_at: AwareDatetime
    route_type: Literal["domestic", "international"]
    status: Literal["scheduled"]
    gate: str | None = Field(default=None, min_length=1, max_length=16)
    cabins: list[CabinSeed] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_flight(self) -> Self:
        if self.origin_code == self.destination_code:
            raise ValueError("Flight origin and destination must differ")
        if self.arrival_at <= self.departure_at:
            raise ValueError("Arrival must be after departure")
        if {cabin.seat_class for cabin in self.cabins} != set(FARE_TIERS_BY_CABIN):
            raise ValueError("Each flight must have all three distinct cabin classes")
        return self


class FlightDataset(SeedRecord):
    schema_version: Literal["1.0.0"]
    dataset_id: str
    status: Literal["fictional_development_data"]
    airline: str = Field(min_length=1, max_length=80)
    description: str
    week_start: date
    week_end: date
    date_reference: Literal["departure_airport_local_time"]
    currency: Literal["USD"]
    price_basis: str
    inventory_note: str
    airports: list[AirportSeed] = Field(min_length=2)
    flights: list[FlightSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if self.week_end != self.week_start + timedelta(days=6):
            raise ValueError("The dataset must cover exactly seven consecutive dates")
        airports = {airport.code: airport for airport in self.airports}
        if len(airports) != len(self.airports):
            raise ValueError("Airport codes must be unique")
        timezones = {code: ZoneInfo(airport.timezone) for code, airport in airports.items()}
        flight_ids: set[UUID] = set()
        flight_keys: set[tuple[str, AwareDatetime]] = set()
        departure_dates: set[date] = set()
        for flight in self.flights:
            if flight.origin_code not in airports or flight.destination_code not in airports:
                raise ValueError("Every flight must reference airports in the dataset")
            key = (flight.flight_number, flight.departure_at)
            if flight.id in flight_ids or key in flight_keys:
                raise ValueError("Flight IDs and flight-number/departure pairs must be unique")
            flight_ids.add(flight.id)
            flight_keys.add(key)
            departure_date = flight.departure_at.astimezone(timezones[flight.origin_code]).date()
            if not self.week_start <= departure_date <= self.week_end:
                raise ValueError("All local departure dates must fall within the sample week")
            departure_dates.add(departure_date)
            domestic = (
                airports[flight.origin_code].country_code
                == airports[flight.destination_code].country_code
            )
            if domestic != (flight.route_type == "domestic"):
                raise ValueError("Route type must match the origin and destination countries")
        if len(departure_dates) != 7:
            raise ValueError("The dataset must include departures on every day of the sample week")
        return self


def load_dataset(path: Path = DEFAULT_DATASET) -> FlightDataset:
    return FlightDataset.model_validate_json(path.read_text(encoding="utf-8"))


async def seed_dataset(database_url: str, dataset: FlightDataset) -> dict[str, int]:
    """Insert missing records in one transaction; existing records are never updated."""
    airports: list[dict[str, object]] = [airport.model_dump() for airport in dataset.airports]
    flights: list[dict[str, object]] = []
    cabins: list[dict[str, object]] = []
    fares: list[dict[str, object]] = []
    for flight in dataset.flights:
        flights.append(
            {
                **flight.model_dump(exclude={"cabins"}),
                "gate": flight.gate or f"A{int(flight.flight_number[4:]) % 20 + 1}",
                "airline": dataset.airline,
            }
        )
        for cabin in flight.cabins:
            cabins.append({"flight_id": flight.id, **cabin.model_dump(exclude={"fares"})})
            for fare in cabin.fares:
                fares.append(
                    {
                        "flight_id": flight.id,
                        "seat_class": cabin.seat_class,
                        "currency": dataset.currency,
                        **fare.model_dump(),
                    }
                )

    rows_by_model: list[tuple[type[Base], list[dict[str, object]]]] = [
        (Airport, airports),
        (Flight, flights),
        (FlightCabin, cabins),
        (FlightFare, fares),
    ]
    engine = create_async_engine(database_url)
    inserted: dict[str, int] = {}
    try:
        async with engine.begin() as connection:
            for model, rows in rows_by_model:
                statement = (
                    insert(model).values(rows).on_conflict_do_nothing().returning(literal(1))
                )
                result = await connection.execute(statement)
                inserted[model.__tablename__] = len(result.scalars().all())
    finally:
        await engine.dispose()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the fictional flight week into PostgreSQL."
    )
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_DATASET, help="Flight dataset JSON path"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Validate the dataset without using a database"
    )
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.file)
    except (OSError, ValidationError, KeyError) as exc:
        parser.error(str(exc))
    print(
        f"Validated {len(dataset.flights)} fictional flights: "
        f"{dataset.week_start} through {dataset.week_end}."
    )
    if args.validate_only:
        return
    inserted = asyncio.run(seed_dataset(Settings().database_url.get_secret_value(), dataset))
    print("Inserted " + ", ".join(f"{count} {table}" for table, count in inserted.items()) + ".")
    print("Existing schedules, prices, and seat availability were preserved.")


if __name__ == "__main__":
    main()
