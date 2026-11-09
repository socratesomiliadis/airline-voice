"""Oracle tests use trusted data rather than the implementation's search response."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from airline_refiner.adapters.api import AirlineAPI
from airline_refiner.outcomes import check_outcomes
from airline_refiner.pipeline.runner import load_scenarios
from airline_refiner.reference import DEFAULT_DATASET, selection_reference

from tests.test_outcomes import case

NOW = "2026-11-06T12:00:00Z"


@pytest.mark.parametrize("selection", ["earliest", "cheapest"])
def test_matching_wrong_search_and_reference_offer_do_not_prove_optimality(selection):
    scenario, sim = case()
    scenario.assertions.selection = selection
    scenario.assertions.tool_parameters = {
        "search_flights": {
            "origin": "SFO",
            "destination": "JFK",
            "seat_class": "economy",
        }
    }
    oracle = selection_reference(scenario, DEFAULT_DATASET, NOW)
    sim.fixture.update(
        business_time=NOW,
        selection_reference=oracle,
        expected_offer={"flight_id": "flight-1", "unit_price_cents": 100},
    )
    # Search, booking and the legacy REST reference agree. The trusted oracle disagrees.
    checks = {c.name: c for c in check_outcomes(scenario, sim)}
    assert checks["selection_oracle"].passed
    assert not checks["selected_offer"].passed


def test_reference_is_captured_without_calling_the_flight_search_endpoint():
    scenario = next(
        s for s in load_scenarios(Path("scenarios/airline.json")) if s.id == "next-available-flight"
    )
    paths = []

    def transport(req):
        paths.append(req.url.path)
        return httpx.Response(200, json={"status": "ok", "business_time": NOW})

    async def run():
        async with httpx.AsyncClient(
            base_url="http://test/", transport=httpx.MockTransport(transport)
        ) as client:
            fixture = await AirlineAPI(client).prepare(scenario, "customer")
            assert fixture["selection_reference"]["source"] == "trusted_fixture"
            assert len(fixture["selection_reference"]["sha256"]) == 64
            assert paths == ["/ready"]

    asyncio.run(run())


def test_oracle_filters_stock_status_time_local_dates_price_and_accepts_objective_ties(tmp_path):
    data = json.loads(DEFAULT_DATASET.read_text())
    base = deepcopy(data["flights"][0])
    base.update(id="eligible", departure_at="2026-11-09T23:30:00-08:00")
    base["cabins"] = [
        {
            "seat_class": "economy",
            "available_seats": 2,
            "fares": [{"fare_tier": "standard", "price_cents": 300}],
        }
    ]
    data["flights"] = [base]
    for identity, changes in [
        ("sold-out", {}),
        ("cancelled", {"status": "cancelled"}),
        ("past", {"departure_at": "2026-11-05T10:00:00-08:00"}),
        ("wrong-local-date", {"departure_at": "2026-11-10T00:01:00-08:00"}),
        ("price-filter", {}),
        ("tie", {}),
    ]:
        flight = deepcopy(base)
        flight.update(id=identity, **changes)
        if identity == "sold-out":
            flight["cabins"][0]["available_seats"] = 1
        if identity == "price-filter":
            flight["cabins"][0]["fares"][0]["price_cents"] = 100
        data["flights"].append(flight)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data))
    scenario, _ = case()
    scenario.assertions.selection = "cheapest"
    scenario.assertions.tool_parameters = {
        "search_flights": {
            "origin": "San Francisco",
            "destination": "LAX",
            "passengers": 2,
            "seat_class": "economy",
            "fare_tier": "standard",
            "min_price_cents": 200,
            "departure_date_from": "2026-11-09",
            "departure_date_to": "2026-11-09",
        }
    }
    oracle = selection_reference(scenario, path, NOW)
    assert oracle["eligible_count"] == 2
    assert {o["flight_id"] for o in oracle["optimal_offers"]} == {"eligible", "tie"}


def test_selected_schedule_must_match_trusted_departure_even_when_flight_id_matches():
    from datetime import datetime, timedelta

    scenario, sim = case()
    scenario.assertions.selection = "earliest"
    scenario.assertions.tool_parameters = {
        "search_flights": {"origin": "SFO", "destination": "JFK", "seat_class": "economy"}
    }
    oracle = selection_reference(scenario, DEFAULT_DATASET, NOW)
    offer = oracle["optimal_offers"][0]
    sim.fixture.update(business_time=NOW, selection_reference=oracle)
    saved = sim.booking_state[0]
    saved["flight"]["id"] = offer["flight_id"]
    saved["flight"]["departure_local"] = offer["departure_at"]
    for field in ("unit_price_cents", "seat_class", "fare_tier"):
        saved[field] = offer[field]
    assert next(c for c in check_outcomes(scenario, sim) if c.name == "selected_offer").passed
    saved["flight"]["departure_local"] = (
        datetime.fromisoformat(offer["departure_at"]) + timedelta(hours=2)
    ).isoformat()
    assert not next(c for c in check_outcomes(scenario, sim) if c.name == "selected_offer").passed
