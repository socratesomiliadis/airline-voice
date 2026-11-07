"""False-positive judges cannot override failed tool or persistence assertions."""

import asyncio
from copy import deepcopy

import pytest
from airline_refiner.config import RefinementConfig
from airline_refiner.models import (
    Evaluation,
    Failure,
    ItemExpectation,
    Scenario,
    Scores,
    Simulation,
)
from airline_refiner.outcomes import check_outcomes
from airline_refiner.pipeline.stages.evaluate import Evaluator


def booking():
    return {
        "id": "booking-1",
        "reference": "ABC123",
        "status": "confirmed",
        "flight": {
            "id": "flight-1",
            "origin": "SFO",
            "destination": "JFK",
            "departure_local": "2026-11-10T06:30:00-08:00",
        },
        "seat_class": "economy",
        "fare_tier": "standard",
        "unit_price_cents": 100,
        "ticket_total_cents": 100,
        "passengers": [{"passenger_id": "customer", "full_name": "Jordan Taylor"}],
        "extras": [],
        "events": [{"charged_cents": 100, "refunded_cents": 0, "credit_cents": 0}],
        "total_charged_cents": 100,
        "total_refunded_cents": 0,
        "total_credit_cents": 0,
    }


def call(name, arguments, result, error=False):
    return {
        "role": "agent",
        "message": "Observed response",
        "tool_calls": [
            {
                "request_id": name,
                "tool_name": name,
                "tool_has_been_called": True,
                "params_as_json": arguments,
            }
        ],
        "tool_results": [
            {"request_id": name, "tool_name": name, "result_value": result, "is_error": error}
        ],
    }


def case():
    saved = booking()
    offer = {
        "flight_id": "flight-1",
        "seat_class": "economy",
        "fare_tier": "standard",
        "unit_price_cents": 100,
    }
    scenario = Scenario(
        id="book",
        goal="Book",
        customer_facts="One passenger",
        expected_outcome="Saved",
        required_tools=["search_flights", "book_flight"],
        assertions={
            "booking_status": "confirmed",
            "origin": "SFO",
            "destination": "JFK",
            "departure_date": "2026-11-10",
            "tool_order": [["search_flights", "book_flight"]],
        },
    )
    args = {**offer, "expected_unit_price_cents": 100, "passengers": deepcopy(saved["passengers"])}
    sim = Simulation(
        scenario_id="book",
        completed=True,
        fixture={"passenger": deepcopy(saved["passengers"][0])},
        transcript=[
            call("search_flights", {}, {"offers": [offer]}),
            call("book_flight", args, deepcopy(saved)),
        ],
        booking_state=[saved],
    )
    return scenario, sim


def test_correct_booking_has_only_passing_checks():
    scenario, sim = case()
    assert all(c.passed for c in check_outcomes(scenario, sim))


@pytest.mark.parametrize(
    "defect",
    [
        "tool_error",
        "tool_payload_error",
        "wrong_date",
        "wrong_flight",
        "wrong_price",
        "wrong_customer",
        "wrong_ledger",
        "invented_quote",
        "wrong_order",
    ],
)
def test_incorrect_booking_cannot_be_accepted_by_an_optimistic_judge(defect):
    scenario, sim = case()
    saved = sim.booking_state[0]
    if defect == "tool_error":
        sim.transcript[-1]["tool_results"][0]["is_error"] = True
    elif defect == "tool_payload_error":
        sim.transcript[-1]["tool_results"][0]["result_value"] = {"detail": "HTTP 500"}
    elif defect == "wrong_date":
        saved["flight"]["departure_local"] = "2026-11-11T06:30:00-08:00"
    elif defect == "wrong_flight":
        saved["flight"]["id"] = "other-flight"
    elif defect == "wrong_price":
        saved["unit_price_cents"] = 200
    elif defect == "wrong_customer":
        saved["passengers"][0]["passenger_id"] = "someone-else"
    elif defect == "wrong_ledger":
        saved["total_charged_cents"] = 200
    elif defect == "invented_quote":
        sim.transcript[0]["tool_results"][0]["result_value"]["offers"][0]["unit_price_cents"] = 200
    else:
        sim.transcript.reverse()
    assert any(not c.passed for c in check_outcomes(scenario, sim))

    class OptimisticJudge:
        async def generate(self, model, instruction, data, schema, validate):
            result = Evaluation(
                scenario_id=scenario.id,
                scores=Scores(
                    understanding=9, api_correctness=9, outcome_confirmation=9, naturalness=9
                ),
                rationale="Optimistic response",
                failures=[],
            )
            validate(result)
            return result

    with pytest.raises(ValueError, match="deterministic"):
        asyncio.run(
            Evaluator(RefinementConfig(), OptimisticJudge()).run(scenario, sim, "Prompt", {}, {})
        )


def test_cancel_result_must_match_saved_cancelled_state_even_with_http_success():
    saved = booking()
    scenario = Scenario(
        id="cancel",
        goal="Cancel",
        customer_facts="Existing booking",
        expected_outcome="Cancelled",
        required_tools=["get_booking", "cancel_booking"],
        assertions={"booking_status": "cancelled"},
    )
    sim = Simulation(
        scenario_id="cancel",
        completed=True,
        fixture={"booking": deepcopy(saved)},
        transcript=[
            call("get_booking", {"reference": "ABC123"}, deepcopy(saved)),
            call("cancel_booking", {"reference": "ABC123"}, {**saved, "status": "cancelled"}),
        ],
        booking_state=[saved],
    )
    assert "mutation_status:ABC123" in {
        c.name for c in check_outcomes(scenario, sim) if not c.passed
    }
    saved["status"] = "cancelled"
    scenario.assertions.full_refund = True
    assert not next(c for c in check_outcomes(scenario, sim) if c.name == "full_refund").passed


def test_new_booking_cannot_undercharge_even_when_the_ledger_is_internally_consistent():
    scenario, sim = case()
    saved = sim.booking_state[0]
    saved["events"][0]["charged_cents"] = saved["total_charged_cents"] = 1
    sim.transcript[-1]["tool_results"][0]["result_value"] = deepcopy(saved)
    assert not next(
        c for c in check_outcomes(scenario, sim) if c.name == "booking_charge:ABC123"
    ).passed


def test_policy_scenario_rejects_even_a_failed_mutation_attempt():
    scenario, sim = case()
    scenario.assertions.forbid_mutations = True
    sim.transcript[-1]["tool_results"][0]["is_error"] = True
    assert not next(c for c in check_outcomes(scenario, sim) if c.name == "no_mutations").passed


def test_counts_fees_seat_preferences_and_selection_have_explicit_assertions():
    scenario, sim = case()
    scenario.assertions.seat_preference = "window"
    scenario.assertions.item_charge_cents = 3500
    scenario.assertions.selection = "cheapest"
    sim.fixture["expected_offer"] = {"unit_price_cents": 50}
    names = {c.name for c in check_outcomes(scenario, sim) if not c.passed}
    assert {"seat_preference", "item_charge", "selected_offer"}.issubset(names)


def test_failed_checks_block_passing_even_at_threshold_one():
    scenario, sim = case()
    sim.booking_state[0]["status"] = "cancelled"

    class Judge:
        async def generate(self, model, instruction, data, schema, validate):
            result = Evaluation(
                scenario_id=scenario.id,
                scores=Scores(
                    understanding=1, api_correctness=1, outcome_confirmation=1, naturalness=1
                ),
                rationale="Failed state",
                failures=[
                    Failure(
                        criterion=c,
                        root_cause="prompt",
                        quote="Observed response",
                        explanation="Outcome did not match",
                        code_faults=[],
                    )
                    for c in ("api_correctness", "outcome_confirmation")
                ],
            )
            validate(result)
            return result

    result = asyncio.run(
        Evaluator(RefinementConfig(pass_score=1), Judge()).run(scenario, sim, "Prompt", {}, {})
    )
    assert not result.passes(1)


@pytest.mark.parametrize("defect", ["count", "fee", "passenger", "measurements"])
def test_saved_bags_must_match_requested_quantity_measurements_passenger_and_fee(defect):
    scenario, sim = case()
    scenario.required_tools = ["get_booking", "add_booking_items"]
    scenario.assertions.tool_order = [["get_booking", "add_booking_items"]]
    scenario.assertions.items = [
        ItemExpectation(item_type="checked_bag", count=2, status="confirmed")
    ]
    scenario.assertions.item_charge_cents = 3500
    initial = deepcopy(sim.booking_state[0])
    sim.fixture["booking"] = initial
    saved = sim.booking_state[0]
    item = {
        "passenger_id": "customer",
        "item_type": "checked_bag",
        "weight_kg": 20,
        "length_cm": 70,
        "width_cm": 45,
        "height_cm": 25,
    }
    saved["extras"] = [{**item, "status": "confirmed", "price_cents": price} for price in [0, 3500]]
    saved["events"][0]["charged_cents"] = saved["total_charged_cents"] = 3600
    args = {"reference": "ABC123", "items": [deepcopy(item), deepcopy(item)]}
    sim.transcript = [
        call("get_booking", {"reference": "ABC123"}, initial),
        call("add_booking_items", args, deepcopy(saved)),
    ]
    assert all(c.passed for c in check_outcomes(scenario, sim))
    if defect == "count":
        saved["extras"].pop()
    elif defect == "fee":
        saved["extras"][1]["price_cents"] = 4000
        saved["events"][0]["charged_cents"] = saved["total_charged_cents"] = 4100
    elif defect == "passenger":
        saved["extras"][1]["passenger_id"] = "someone-else"
    else:
        saved["extras"][1]["weight_kg"] = 25
    sim.transcript[-1]["tool_results"][0]["result_value"] = deepcopy(saved)
    assert any(not c.passed for c in check_outcomes(scenario, sim))
