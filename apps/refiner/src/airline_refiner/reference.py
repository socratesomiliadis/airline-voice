"""Selection oracle over trusted fixture JSON; no airline search/service imports."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from airline_refiner.errors import RefinementError
from airline_refiner.models import Scenario

DEFAULT_DATASET = Path("data/flights/week_2026_11_09.json")


def selection_reference(
    scenario: Scenario, dataset_path: Path, business_time: str
) -> dict[str, Any]:
    """Calculate all objective ties from the fixture, using departure-airport dates.

    This oracle assumes a dedicated, seeded demonstration database, with no external
    inventory writers. Fixture stock is deliberately not sourced from the search API.
    """
    raw = dataset_path.read_bytes()
    dataset = json.loads(raw)
    now = datetime.fromisoformat(business_time)
    if now.tzinfo is None:
        raise ValueError("Selection oracle requires an aware business time")
    query: dict[str, Any] = scenario.assertions.tool_parameters.get("search_flights", {})
    airports = {a["code"]: a for a in dataset["airports"]}
    offers = []
    for flight in dataset["flights"]:
        departure = datetime.fromisoformat(flight["departure_at"])
        if flight["status"] != "scheduled" or departure <= now:
            continue
        if any(
            query.get(key)
            and str(query[key]).casefold()
            not in {
                flight[key + "_code"].casefold(),
                airports[flight[key + "_code"]]["city"].casefold(),
            }
            for key in ("origin", "destination")
        ):
            continue
        local_date = (
            departure.astimezone(ZoneInfo(airports[flight["origin_code"]]["timezone"]))
            .date()
            .isoformat()
        )
        if (
            (query.get("departure_date") and local_date != query["departure_date"])
            or (query.get("departure_date_from") and local_date < str(query["departure_date_from"]))
            or (query.get("departure_date_to") and local_date > str(query["departure_date_to"]))
        ):
            continue
        for cabin in flight["cabins"]:
            if cabin["available_seats"] < int(query.get("passengers") or 1) or (
                query.get("seat_class") and cabin["seat_class"] != query["seat_class"]
            ):
                continue
            for fare in cabin["fares"]:
                if (
                    (query.get("fare_tier") and fare["fare_tier"] != query["fare_tier"])
                    or (
                        query.get("min_price_cents") is not None
                        and fare["price_cents"] < int(query["min_price_cents"])
                    )
                    or (
                        query.get("max_price_cents") is not None
                        and fare["price_cents"] > int(query["max_price_cents"])
                    )
                ):
                    continue
                offers.append(
                    {
                        "flight_id": flight["id"],
                        "departure_at": departure.isoformat(),
                        "seat_class": cabin["seat_class"],
                        "fare_tier": fare["fare_tier"],
                        "unit_price_cents": fare["price_cents"],
                    }
                )
    if not offers:
        raise RefinementError("No eligible trusted fixture offers for selection assertion")

    def objective(offer: dict[str, Any]) -> Any:
        return (
            datetime.fromisoformat(offer["departure_at"])
            if scenario.assertions.selection == "earliest"
            else offer["unit_price_cents"]
        )

    best = min(objective(offer) for offer in offers)
    return {
        "source": "trusted_fixture",
        "dataset_id": dataset["dataset_id"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "business_time": business_time,
        "query": query,
        "eligible_count": len(offers),
        "optimal_offers": [offer for offer in offers if objective(offer) == best],
    }
