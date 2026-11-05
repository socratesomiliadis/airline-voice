"""Prevent policy data from drifting from the flight inventory and its terminology."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from airline_api.infrastructure.database.base import Base
from airline_api.infrastructure.database.seed import load_dataset

POLICY_FILES = sorted(Path("knowledge").glob("*.json"))


def load_policies() -> dict[str, Any]:
    return {path.stem: json.loads(path.read_text()) for path in POLICY_FILES}


def walk_references(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("rule_id") or key == "takes_precedence_over":
                yield item
            elif key.endswith("rule_ids"):
                yield from item
            yield from walk_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_references(item)


@pytest.mark.parametrize("path", POLICY_FILES, ids=lambda path: path.stem)
def test_policy_scope_matches_every_offered_cabin_fare_and_route(path: Path) -> None:
    document = json.loads(path.read_text())
    dataset = load_dataset()
    scope = document["scope"]
    offered_tiers: dict[str, set[str]] = {}
    for flight in dataset.flights:
        assert flight.route_type in scope["route_types"]
        for cabin in flight.cabins:
            offered_tiers.setdefault(cabin.seat_class, set()).update(
                fare.fare_tier for fare in cabin.fares
            )
    assert set(scope["route_types"]) == {flight.route_type for flight in dataset.flights}
    assert set(scope["seat_classes"]) == set(offered_tiers)
    assert set(scope["fare_tiers"]) == set.union(*offered_tiers.values())
    assert {
        key: set(tiers) for key, tiers in scope["fare_tiers_by_seat_class"].items()
    } == offered_tiers
    assert document["airline"]["name"] == scope["operating_carrier"] == dataset.airline
    assert document["airline"]["fictional"] is True
    assert document["status"] == dataset.status
    assert scope["currency"] == dataset.currency


@pytest.mark.parametrize("path", POLICY_FILES, ids=lambda path: path.stem)
def test_inventory_reference_matches_the_week_and_real_database_fields(path: Path) -> None:
    document = json.loads(path.read_text())
    dataset = load_dataset()
    reference = document["inventory_reference"]
    assert reference["seed_dataset_id"] == dataset.dataset_id
    assert Path(reference["seed_dataset_path"]).is_file()
    assert reference["sample_departure_week"] == {
        "start": dataset.week_start.isoformat(),
        "end": dataset.week_end.isoformat(),
        "date_reference": dataset.date_reference,
    }
    assert set(reference["sample_airport_codes"]) == {airport.code for airport in dataset.airports}
    assert {
        route_type: set(routes) for route_type, routes in reference["sample_route_examples"].items()
    } == {
        route_type: {
            f"{flight.origin_code}-{flight.destination_code}"
            for flight in dataset.flights
            if flight.route_type == route_type
        }
        for route_type in {flight.route_type for flight in dataset.flights}
    }
    for field in reference["source_fields"].values():
        table, column = field.split(".")
        assert column in Base.metadata.tables[table].columns, f"Unknown inventory field: {field}"
    assert reference["fare_price_unit"] == "minor_currency_units"
    assert document["scope"]["fee_amount_unit"] == "major_currency_units"
    assert reference["minor_units_per_currency_unit"] == 100
    assert reference["fare_price_basis"] == "per_adult_passenger_per_flight_segment"
    assert reference["fare_includes_sample_taxes"] is True
    assert reference["fare_includes_optional_service_fees"] is False


def test_every_seeded_offer_has_baggage_change_refund_and_check_in_rules() -> None:
    policies = load_policies()
    baggage = {rule["id"]: rule["details"] for rule in policies["baggage"]["policy"]["rules"]}
    changes = {
        rule["id"]: rule["details"] for rule in policies["booking_changes"]["policy"]["rules"]
    }
    refunds = {
        rule["id"]: rule["details"]
        for rule in policies["cancellation_and_refunds"]["policy"]["rules"]
    }
    check_in = {rule["id"]: rule["details"] for rule in policies["check_in"]["policy"]["rules"]}
    for flight in load_dataset().flights:
        for cabin in flight.cabins:
            for fare in cabin.fares:
                tier = fare.fare_tier
                route = flight.route_type
                assert (
                    baggage["baggage.checked_allowance"]["included_pieces_by_fare"][tier][route]
                    >= 0
                )
                assert (
                    baggage["baggage.checked_allowance"]["standard_weight_limit_kg_by_fare"][tier]
                    > 0
                )
                assert (
                    "refund_type" in refunds["cancellation.voluntary_by_fare"]["fare_rules"][tier]
                )
                change_rule = changes["changes.voluntary"]["fare_rules"][tier]
                if change_rule["changes_allowed"]:
                    assert change_rule["change_fee_usd"][route] >= 0
                assert check_in["check_in.online"]["closes_minutes_before_departure"][route] > 0
                assert (
                    check_in["check_in.airport_and_bag_drop"][
                        "bag_drop_closes_minutes_before_departure"
                    ][route]
                    > 0
                )
                assert (
                    check_in["check_in.boarding"]["gate_closes_minutes_before_departure"][route] > 0
                )


def test_international_pet_requirements_cover_the_international_sample_routes() -> None:
    policy = load_policies()["pet_policy"]["policy"]
    rules = {rule["id"]: rule["details"] for rule in policy["rules"]}
    expected = {
        f"{flight.origin_code}-{flight.destination_code}"
        for flight in load_dataset().flights
        if flight.route_type == "international"
    }
    assert (
        set(rules["pets.eligibility"]["international_sample_routes_requiring_confirmation"])
        == expected
    )
    assert rules["pets.eligibility"]["international_travel"] == "requires_manual_confirmation"
    assert (
        rules["pets.reservations_and_fees"]["pet_spaces_tracked_in_flight_cabin_inventory"] is False
    )
    assert rules["pets.reservations_and_fees"]["pet_fee_included_in_ticket_price_cents"] is False


def test_policy_cross_references_and_shared_context_are_consistent() -> None:
    policies = list(load_policies().values())
    assert len(policies) == 6
    ids = [rule["id"] for document in policies for rule in document["policy"]["rules"]]
    assert len(ids) == len(set(ids))
    assert set(walk_references(policies)) <= set(ids)
    for document in policies[1:]:
        assert document["scope"] == policies[0]["scope"]
        assert document["inventory_reference"] == policies[0]["inventory_reference"]
