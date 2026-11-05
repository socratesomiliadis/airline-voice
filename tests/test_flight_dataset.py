"""Validate the fictional schedule and reject data that cannot be safely imported."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from airline_api.infrastructure.database.seed import DEFAULT_DATASET, FlightDataset, load_dataset
from pydantic import ValidationError


def test_dataset_covers_one_week_and_multiple_destinations() -> None:
    dataset = load_dataset()
    airports = {airport.code: airport for airport in dataset.airports}
    dates = {
        flight.departure_at.astimezone(ZoneInfo(airports[flight.origin_code].timezone)).date()
        for flight in dataset.flights
    }
    assert dataset.week_start == date(2026, 11, 9)
    assert dataset.week_end == date(2026, 11, 15)
    assert len(dates) == 7
    assert len(dataset.flights) == 112
    assert len(airports) == 7
    assert {flight.route_type for flight in dataset.flights} == {"domestic", "international"}
    assert len({flight.departure_at.timetz() for flight in dataset.flights}) > 3
    assert all(
        any(cabin.available_seats > 0 for cabin in flight.cabins) for flight in dataset.flights
    )


def test_fares_match_knowledge_base_and_share_cabin_inventory() -> None:
    dataset = load_dataset()
    policy = json.loads(Path("knowledge/baggage.json").read_text())
    policy_fares = set(policy["scope"]["fare_tiers"])
    all_fares = set()
    for flight in dataset.flights:
        assert len(flight.cabins) == 3
        for cabin in flight.cabins:
            all_fares.update(fare.fare_tier for fare in cabin.fares)
            assert 0 <= cabin.available_seats <= cabin.capacity
            assert len({fare.price_cents for fare in cabin.fares}) == len(cabin.fares)
            assert all(fare.price_cents > 0 for fare in cabin.fares)
    assert all_fares == policy_fares
    assert sum(len(cabin.fares) for flight in dataset.flights for cabin in flight.cabins) == 672


def test_overnight_flights_have_correct_local_arrival_dates() -> None:
    flight = next(flight for flight in load_dataset().flights if flight.flight_number == "DEMO601")
    assert flight.departure_at.date() == date(2026, 11, 9)
    assert flight.arrival_at.date() == date(2026, 11, 10)
    assert (flight.arrival_at - flight.departure_at).total_seconds() == 630 * 60


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_flight",
        "unknown_airport",
        "arrival_before_departure",
        "naive_departure",
        "outside_week",
        "wrong_route_type",
        "invalid_inventory",
        "invalid_cabin_fare",
        "fractional_price",
        "negative_price",
    ],
)
def test_rejects_invalid_seed_data(case: str) -> None:
    data = deepcopy(json.loads(DEFAULT_DATASET.read_text()))
    flight = data["flights"][0]
    match case:
        case "duplicate_flight":
            data["flights"].append(deepcopy(flight))
        case "unknown_airport":
            flight["destination_code"] = "ZZZ"
        case "arrival_before_departure":
            flight["arrival_at"] = "2026-11-08T06:00:00-08:00"
        case "naive_departure":
            flight["departure_at"] = "2026-11-09T07:00:00"
        case "outside_week":
            flight["departure_at"] = "2026-11-08T07:00:00-08:00"
        case "wrong_route_type":
            flight["route_type"] = "international"
        case "invalid_inventory":
            flight["cabins"][0]["available_seats"] = flight["cabins"][0]["capacity"] + 1
        case "invalid_cabin_fare":
            flight["cabins"][0]["fares"][0]["fare_tier"] = "business"
        case "fractional_price":
            flight["cabins"][0]["fares"][0]["price_cents"] = 100.5
        case "negative_price":
            flight["cabins"][0]["fares"][0]["price_cents"] = -1
    with pytest.raises(ValidationError):
        FlightDataset.model_validate(data)
