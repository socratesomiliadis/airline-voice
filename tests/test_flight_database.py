"""PostgreSQL integration checks using an isolated, disposable test database."""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from uuid import uuid4

import pytest
from airline_api.infrastructure.database.models import Flight, FlightCabin, FlightFare
from airline_api.infrastructure.database.seed import load_dataset, seed_dataset
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


def migrate(database_url: str, *arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", *arguments],
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def postgres_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("Set TEST_DATABASE_URL to run the isolated PostgreSQL integration test")
    database_name = f"airline_flights_test_{uuid4().hex}"

    async def manage_database(create: bool) -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                if create:
                    await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
                else:
                    await connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        finally:
            await engine.dispose()

    asyncio.run(manage_database(create=True))
    database_url = (
        make_url(admin_url).set(database=database_name).render_as_string(hide_password=False)
    )
    try:
        migrate(database_url, "upgrade", "head")
        yield database_url
    finally:
        asyncio.run(manage_database(create=False))


def test_postgres_migration_seed_inventory_and_constraints(postgres_url: str) -> None:
    async def scenario() -> None:
        dataset = load_dataset()
        expected = {"airports": 7, "flights": 112, "flight_cabins": 336, "flight_fares": 672}
        assert await seed_dataset(postgres_url, dataset) == expected
        assert await seed_dataset(postgres_url, dataset) == dict.fromkeys(expected, 0)
        flight = dataset.flights[0]
        cabin = flight.cabins[0]
        fare = cabin.fares[0]
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    update(FlightCabin)
                    .where(
                        FlightCabin.flight_id == flight.id,
                        FlightCabin.seat_class == cabin.seat_class,
                    )
                    .values(available_seats=FlightCabin.available_seats - 1)
                )
                await connection.execute(
                    update(FlightFare)
                    .where(
                        FlightFare.flight_id == flight.id,
                        FlightFare.seat_class == cabin.seat_class,
                        FlightFare.fare_tier == fare.fare_tier,
                    )
                    .values(price_cents=FlightFare.price_cents + 100)
                )
                await connection.execute(
                    update(Flight).where(Flight.id == flight.id).values(status="cancelled")
                )
            assert await seed_dataset(postgres_url, dataset) == dict.fromkeys(expected, 0)
            async with engine.begin() as connection:
                assert await connection.scalar(select(func.count()).select_from(Flight)) == 112
                assert (
                    await connection.scalar(
                        select(FlightCabin.available_seats).where(
                            FlightCabin.flight_id == flight.id,
                            FlightCabin.seat_class == cabin.seat_class,
                        )
                    )
                    == cabin.available_seats - 1
                )
                assert (
                    await connection.scalar(
                        select(FlightFare.price_cents).where(
                            FlightFare.flight_id == flight.id,
                            FlightFare.seat_class == cabin.seat_class,
                            FlightFare.fare_tier == fare.fare_tier,
                        )
                    )
                    == fare.price_cents + 100
                )
                assert (
                    await connection.scalar(select(Flight.status).where(Flight.id == flight.id))
                    == "cancelled"
                )

                for invalid_seats in [-1, cabin.capacity + 1]:
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                update(FlightCabin)
                                .where(
                                    FlightCabin.flight_id == flight.id,
                                    FlightCabin.seat_class == cabin.seat_class,
                                )
                                .values(available_seats=invalid_seats)
                            )
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(
                            update(FlightFare)
                            .where(FlightFare.flight_id == flight.id)
                            .values(price_cents=-1)
                        )
        finally:
            await engine.dispose()

    asyncio.run(scenario())
    migrate(postgres_url, "check")
    migrate(postgres_url, "downgrade", "base")
    migrate(postgres_url, "upgrade", "head")
