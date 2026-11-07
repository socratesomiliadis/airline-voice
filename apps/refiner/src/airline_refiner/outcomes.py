"""Deterministic acceptance checks over authoritative tool results and saved state."""

import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from airline_refiner.models import OutcomeCheck, Scenario, Simulation

MUTATIONS = {"book_flight", "cancel_booking", "reschedule_booking", "add_booking_items"}
WEBHOOKS = MUTATIONS | {"search_flights", "get_booking", "get_flight_information"}


def decode(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def valid_result(name: str, data: dict[str, Any] | None) -> bool:
    if data is None or "error" in data or "detail" in data:
        return False
    if name == "search_flights":
        return isinstance(data.get("offers"), list)
    if name == "get_flight_information":
        return isinstance(data.get("flights"), list)
    return (
        isinstance(data.get("reference"), str)
        and bool(data["reference"])
        and data.get("status") in {"confirmed", "cancelled"}
        and isinstance(data.get("flight"), dict)
        and isinstance(data.get("passengers"), list)
        and bool(data["passengers"])
    )


@dataclass
class Invocation:
    name: str
    index: int
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    successful: bool


def invocations(simulation: Simulation) -> list[Invocation]:
    calls = [
        call
        for turn in simulation.transcript
        for call in turn.get("tool_calls") or []
        if call.get("tool_has_been_called") is True and call.get("tool_name") in WEBHOOKS
    ]
    results = [
        result for turn in simulation.transcript for result in turn.get("tool_results") or []
    ]
    output = []
    for index, call in enumerate(calls):
        matches = [r for r in results if r.get("request_id") == call.get("request_id")]
        if not call.get("request_id"):
            matches = [r for r in results if r.get("tool_name") == call.get("tool_name")]
        result = matches[0] if len(matches) == 1 else None
        data = decode(result.get("result_value")) if result else None
        output.append(
            Invocation(
                name=call["tool_name"],
                index=index,
                arguments=decode(call.get("params_as_json")) or {},
                result=data,
                successful=bool(
                    result
                    and valid_result(call["tool_name"], data)
                    and not result.get("is_error")
                    and not result.get("is_blocked")
                    and result.get("tool_has_been_called") is not False
                ),
            )
        )
    return output


def check_outcomes(scenario: Scenario, simulation: Simulation) -> list[OutcomeCheck]:
    checks: list[OutcomeCheck] = []

    def add(name: str, passed: bool, explanation: str, evidence: Any = None) -> None:
        checks.append(
            OutcomeCheck(
                name=name,
                passed=bool(passed),
                explanation=explanation,
                evidence=""
                if passed
                else (
                    evidence
                    if isinstance(evidence, str)
                    else json.dumps(evidence, ensure_ascii=False)
                ),
            )
        )

    calls = invocations(simulation)
    add(
        "complete_simulation",
        simulation.completed
        and bool(simulation.transcript)
        and not simulation.errors
        and not simulation.cleanup_errors,
        "Conversation, transcript, and fixture cleanup must complete without errors.",
        simulation.transcript,
    )
    if any(c.name in MUTATIONS for c in calls) or MUTATIONS.intersection(scenario.required_tools):
        add(
            "booking_evidence",
            bool(simulation.booking_state),
            "Mutation scenarios require persisted booking evidence.",
            simulation.transcript,
        )
    latest = {call.name: call for call in calls}
    for lookup in calls:
        if lookup.name == "get_booking" and lookup.successful:
            data = lookup.result or {}
            locator = str(lookup.arguments.get("reference", "")).strip().casefold()
            add(
                f"lookup_reference:{lookup.index}",
                bool(locator)
                and locator
                in {str(data.get("reference", "")).casefold(), str(data.get("id", "")).casefold()},
                "Booking lookup must return the requested reference or UUID.",
                simulation.transcript,
            )
    for name in sorted(set(scenario.required_tools) | (MUTATIONS & latest.keys())):
        call = latest.get(name)
        add(
            f"tool_success:{name}",
            call is not None and call.successful,
            f"The final {name} invocation must have an unblocked, successful JSON result.",
            simulation.transcript,
        )
    expected = scenario.assertions
    if expected.forbid_mutations:
        add(
            "no_mutations",
            not any(c.name in MUTATIONS for c in calls),
            "This scenario forbids booking mutations, including rejected attempts.",
            simulation.transcript,
        )
    for order in expected.tool_order:
        if len(order) != 2:
            raise ValueError("tool_order entries must contain [before, after]")
        before, after = order
        after_calls = [c for c in calls if c.name == after and c.successful]
        add(
            f"tool_order:{before}:{after}",
            bool(after_calls)
            and all(
                any(c.name == before and c.successful and c.index < target.index for c in calls)
                for target in after_calls
            ),
            f"A successful {before} must precede {after}.",
            simulation.transcript,
        )
    defaults: dict[str, Any] = {"sort_by": "departure", "passengers": 1, "offset": 0}
    for name, parameters in expected.tool_parameters.items():
        call = latest.get(name)
        for key, value in parameters.items():
            actual = call.arguments.get(key, defaults.get(key)) if call else None
            if key == "flight_number" and isinstance(actual, str) and isinstance(value, str):
                actual, value = actual.upper(), value.upper()
            add(
                f"tool_parameter:{name}:{key}",
                call is not None and actual == value,
                f"{name}.{key} must be {value!r}; observed {actual!r}.",
                simulation.transcript,
            )
    information = latest.get("get_flight_information")
    if information and information.successful:
        flights = (information.result or {}).get("flights") or []
        add(
            "flight_information_data",
            bool(flights)
            and all(
                str(f.get("flight_number", "")).upper()
                == str(information.arguments.get("flight_number", "")).upper()
                and str(f.get("departure_local", ""))[:10]
                == information.arguments.get("departure_date")
                and f.get("status") in {"scheduled", "cancelled", "departed", "arrived"}
                for f in flights
            ),
            "Flight information must identify the queried flight/date and a valid saved status.",
            simulation.transcript,
        )

    saved = simulation.booking_state
    by_reference = {str(b.get("reference", "")).upper(): b for b in saved}
    by_id = {str(b.get("id")): b for b in saved if b.get("id")}
    last_mutations: dict[str, Invocation] = {}
    for call in calls:
        if call.name in MUTATIONS and call.successful and call.result:
            reference = str(call.result.get("reference", "")).upper()
            add(
                f"persisted:{call.index}",
                bool(reference and reference in by_reference),
                "Each successful mutation must be visible in persisted booking evidence.",
                saved,
            )
            last_mutations[reference] = call
    for reference, call in last_mutations.items():
        booking = by_reference.get(reference)
        if not booking:
            continue
        args = call.arguments
        response = call.result or {}
        response_keys = (
            "status",
            "seat_class",
            "fare_tier",
            "unit_price_cents",
            "passengers",
            "extras",
            "total_charged_cents",
            "total_refunded_cents",
            "total_credit_cents",
        )
        add(
            f"mutation_response:{reference}",
            all(response.get(key) == booking.get(key) for key in response_keys),
            "The final mutation response must agree with persisted booking and monetary state.",
            booking,
        )
        status = "cancelled" if call.name == "cancel_booking" else "confirmed"
        add(
            f"mutation_status:{reference}",
            booking.get("status") == status,
            f"{call.name} must persist status={status}.",
            booking,
        )
        if call.name != "book_flight":
            locator = str(args.get("reference", ""))
            target = by_reference.get(locator.upper()) or by_id.get(locator)
            add(
                f"mutation_reference:{reference}",
                target is booking,
                "The mutation must affect the requested booking reference.",
                booking,
            )
            if "get_booking" in scenario.required_tools:
                add(
                    f"retrieved_target:{reference}",
                    any(
                        c.name == "get_booking"
                        and c.successful
                        and c.index < call.index
                        and str((c.result or {}).get("reference", "")).upper() == reference
                        for c in calls
                    ),
                    "Retrieve the same booking before mutating it.",
                    simulation.transcript,
                )
        if call.name in {"book_flight", "reschedule_booking"}:
            flight = booking.get("flight") or {}
            for key, actual in [
                ("flight_id", flight.get("id")),
                ("seat_class", booking.get("seat_class")),
                ("fare_tier", booking.get("fare_tier")),
            ]:
                add(
                    f"quote:{reference}:{key}",
                    actual == args.get(key),
                    f"Saved {key} must match the selected quote.",
                    booking,
                )
            change: dict[str, Any] = next(
                (
                    e
                    for e in reversed(booking.get("events", []))
                    if e.get("action") == "rescheduled"
                ),
                {},
            )
            disrupted = change.get("details", {}).get("airline_disruption")
            add(
                f"quote:{reference}:price",
                bool(disrupted)
                or booking.get("unit_price_cents") == args.get("expected_unit_price_cents"),
                "The saved unit price must match the accepted quote unless disruption waives it.",
                booking,
            )
            if "search_flights" in scenario.required_tools:
                add(
                    f"searched_quote:{reference}",
                    any(
                        c.name == "search_flights"
                        and c.successful
                        and c.index < call.index
                        and any(
                            all(
                                offer.get(key) == args.get(key)
                                for key in ("flight_id", "seat_class", "fare_tier")
                            )
                            and offer.get("unit_price_cents")
                            == args.get("expected_unit_price_cents")
                            for offer in (c.result or {}).get("offers", [])
                        )
                        for c in calls
                    ),
                    "The accepted mutation quote must have been returned by a preceding search.",
                    simulation.transcript,
                )
        if call.name == "book_flight":
            requested = args.get("passengers") or []
            actual_passengers = booking.get("passengers") or []

            def identities(items: list[dict[str, Any]]) -> list[tuple[str, ...]]:
                return sorted(
                    tuple(
                        str(item.get(k) or "").casefold()
                        for k in ("passenger_id", "full_name", "seat_preference")
                    )
                    for item in items
                )

            add(
                f"passengers:{reference}",
                bool(requested) and identities(requested) == identities(actual_passengers),
                "Saved passengers and seat preferences must match the booking request.",
                booking,
            )
            unit = booking.get("unit_price_cents")
            ticket = booking.get("ticket_total_cents")
            add(
                f"ticket_total:{reference}",
                type(unit) is int and ticket == unit * len(actual_passengers),
                "Ticket total must equal the accepted unit price times the passenger count.",
                booking,
            )
            add(
                f"booking_charge:{reference}",
                booking.get("total_charged_cents") == ticket
                and booking.get("total_refunded_cents") == booking.get("total_credit_cents") == 0,
                "A new ticket must charge its accepted total, with no invented refunds or credits.",
                booking,
            )
        if call.name == "add_booking_items":

            def item_signature(item: dict[str, Any]) -> tuple[str, ...]:
                measurements = []
                for key in ("weight_kg", "length_cm", "width_cm", "height_cm"):
                    try:
                        value = (
                            str(Decimal(str(item[key])).normalize())
                            if item.get(key) is not None
                            else ""
                        )
                    except InvalidOperation:
                        value = "invalid"
                    measurements.append(value)
                return (
                    str(item.get("passenger_id", "")).casefold(),
                    str(item.get("item_type")),
                    *measurements,
                )

            requested_counts = Counter(item_signature(i) for i in args.get("items", []))
            saved_counts = Counter(
                item_signature(i)
                for i in booking.get("extras", [])
                if i.get("status") in {"confirmed", "pending_confirmation"}
            )
            add(
                f"items:{reference}",
                bool(requested_counts)
                and all(saved_counts[key] >= count for key, count in requested_counts.items()),
                "Requested items must exist for the requested passengers.",
                booking,
            )

    needs_booking = any(
        value is not None
        for value in (
            expected.booking_status,
            expected.origin,
            expected.destination,
            expected.departure_date,
            expected.seat_class,
            expected.fare_tier,
            expected.seat_preference,
            expected.item_charge_cents,
            expected.selection,
        )
    ) or bool(expected.unchanged_booking or expected.items or expected.full_refund)
    fixture_booking = simulation.fixture.get("booking")
    booking = (
        by_reference.get(str(fixture_booking.get("reference", "")).upper())
        if fixture_booking
        else saved[0]
        if len(saved) == 1
        else None
    )
    if needs_booking:
        add(
            "target_booking",
            booking is not None and len(saved) == 1,
            "Exactly the expected booking must be captured, with no unexpected extra bookings.",
            saved,
        )
    if booking is None:
        return checks
    flight = booking.get("flight") or {}
    fields = {
        "status": (expected.booking_status, booking.get("status")),
        "origin": (expected.origin, flight.get("origin")),
        "destination": (expected.destination, flight.get("destination")),
        "departure_date": (expected.departure_date, str(flight.get("departure_local", ""))[:10]),
        "seat_class": (expected.seat_class, booking.get("seat_class")),
        "fare_tier": (expected.fare_tier, booking.get("fare_tier")),
    }
    for name, (wanted, actual) in fields.items():
        if wanted is not None:
            add(
                f"booking:{name}",
                actual == wanted,
                f"Saved {name} must be {wanted!r}; observed {actual!r}.",
                booking,
            )
    identity = simulation.fixture.get("passenger") or {}
    if identity.get("passenger_id") and needs_booking:
        passengers = booking.get("passengers") or []
        add(
            "customer_identity",
            len(passengers) == 1 and passengers[0].get("passenger_id") == identity["passenger_id"],
            "The booking must belong to the fixture customer.",
            booking,
        )
    if expected.seat_preference:
        add(
            "seat_preference",
            bool(booking.get("passengers"))
            and all(
                p.get("seat_preference") == expected.seat_preference
                and p.get("seat_preference_status") == "requested"
                for p in booking["passengers"]
            ),
            "The requested seat preference must be persisted with requested status.",
            booking,
        )
    for item in expected.items:
        matching = [
            i
            for i in booking.get("extras", [])
            if i.get("item_type") == item.item_type
            and i.get("status") == item.status
            and i.get("passenger_id") == identity.get("passenger_id")
        ]
        add(
            f"item_count:{item.item_type}",
            len(matching) == item.count,
            f"Expected {item.count} customer items: {item.item_type}, status={item.status}.",
            booking,
        )
    if expected.item_charge_cents is not None:
        charged = sum(i.get("price_cents", 0) for i in booking.get("extras", []))
        add(
            "item_charge",
            charged == expected.item_charge_cents,
            f"Item charges must total {expected.item_charge_cents} cents; observed {charged}.",
            booking,
        )
    if expected.unchanged_booking:
        keys = ("status", "flight", "seat_class", "fare_tier", "passengers", "extras", "events")
        add(
            "unchanged_booking",
            bool(fixture_booking)
            and all(booking.get(key) == (fixture_booking or {}).get(key) for key in keys),
            "The existing booking must remain unchanged.",
            booking,
        )
    if expected.full_refund:
        initial = fixture_booking or {}
        paid = initial.get("ticket_total_cents", 0) + sum(
            i.get("price_cents", 0)
            for i in initial.get("extras", [])
            if i.get("status") == "confirmed"
        )
        refund = booking.get("total_refunded_cents", 0) - initial.get("total_refunded_cents", 0)
        add(
            "full_refund",
            bool(fixture_booking) and paid > 0 and refund == paid,
            "This refundable fixture must refund its recorded paid ticket and unused item value.",
            booking,
        )
    if expected.selection:
        offer = simulation.fixture.get("expected_offer") or {}
        add(
            "selection_oracle",
            bool(offer),
            "Selection needs an independently captured REST offer.",
            simulation.fixture,
        )
        if offer:
            correct = (
                flight.get("id") == offer.get("flight_id")
                if expected.selection == "earliest"
                else booking.get("unit_price_cents") == offer.get("unit_price_cents")
            )
            add(
                "selected_offer",
                correct,
                f"Booking must select the {expected.selection} eligible offer.",
                booking,
            )
        search = expected.tool_parameters.get("search_flights", {})
        local_date = str(flight.get("departure_local", ""))[:10]
        for key in ("departure_date_from", "departure_date_to"):
            if search.get(key) is not None:
                bound = str(search[key])
                in_range = (
                    local_date >= bound if key == "departure_date_from" else local_date <= bound
                )
                add(
                    f"selected_window:{key}",
                    bool(local_date) and in_range,
                    "The selected flight must depart inside the requested local date window.",
                    booking,
                )
    extras = booking.get("extras", [])
    add(
        "item_prices",
        all(
            type(i.get("price_cents")) is int
            and i["price_cents"] >= 0
            and (i.get("status") != "pending_confirmation" or i["price_cents"] == 0)
            for i in extras
        ),
        "Item charges must be nonnegative integer cents; pending items cannot be charged.",
        booking,
    )
    for name in ("charged", "refunded", "credit"):
        key = name + "_cents"
        amounts = [e.get(key) for e in booking.get("events", [])]
        valid = bool(amounts) and all(type(v) is int and v >= 0 for v in amounts)
        add(
            f"ledger:{name}",
            valid and sum(amounts) == booking.get("total_" + key),
            f"Saved total_{key} must equal its nonnegative integer ledger entries.",
            booking,
        )
    return checks
