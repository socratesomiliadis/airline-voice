"""Real PostgreSQL booking, webhook, restart, rollback, and concurrent request tests."""

import asyncio
import hashlib
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from airline_api.core.config import Settings
from airline_api.infrastructure.database.seed import load_dataset, seed_dataset
from airline_api.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HEADERS = {"X-Agent-Api-Key": "test-agent-key"}
TOOLS = "/api/v1/voice/webhooks/elevenlabs"


def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=SecretStr(database_url),
        agent_api_key=SecretStr(HEADERS["X-Agent-Api-Key"]),
        simulation_now="2026-11-05T12:00:00Z",
    )


@pytest.fixture
def client(postgres_url: str) -> Iterator[TestClient]:
    asyncio.run(seed_dataset(postgres_url, load_dataset()))
    with TestClient(create_app(settings(postgres_url)), headers=HEADERS) as instance:
        yield instance


def sql(database_url: str, statement: str, **parameters: Any) -> list[Any]:
    async def execute() -> list[Any]:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(statement), parameters)
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(execute())


def offers(
    client: TestClient,
    day: str = "2026-11-09",
    destination: str = "LAX",
    seat_class: str = "economy",
    tier: str = "standard",
) -> list[dict[str, Any]]:
    result = client.get(
        "/api/v1/flights",
        params={
            "origin": "SFO",
            "destination": destination,
            "departure_date": day,
            "seat_class": seat_class,
            "fare_tier": tier,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()["offers"]


def payload(
    offer: dict[str, Any], passenger: str = "customer-1", key: str | None = None
) -> dict[str, Any]:
    return {
        "idempotency_key": key or str(uuid4()),
        "caller_id": "caller-one",
        "flight_id": offer["flight_id"],
        "seat_class": offer["seat_class"],
        "fare_tier": offer["fare_tier"],
        "expected_unit_price_cents": offer["unit_price_cents"],
        "passengers": [{"passenger_id": passenger, "full_name": "Sample Passenger"}],
    }


def book(
    client: TestClient, offer: dict[str, Any], passenger: str = "customer-1"
) -> dict[str, Any]:
    result = client.post("/api/v1/bookings", json=payload(offer, passenger))
    assert result.status_code == 201, result.text
    return result.json()


def action(**values: Any) -> dict[str, Any]:
    return {"idempotency_key": str(uuid4()), "caller_id": "caller-two", **values}


def replacement(offer: dict[str, Any]) -> dict[str, Any]:
    return action(
        flight_id=offer["flight_id"],
        seat_class=offer["seat_class"],
        fare_tier=offer["fare_tier"],
        expected_unit_price_cents=offer["unit_price_cents"],
    )


def bag(passenger: str = "customer-1", **values: Any) -> dict[str, Any]:
    return {
        "passenger_id": passenger,
        "item_type": "checked_bag",
        "weight_kg": 20,
        "length_cm": 60,
        "width_cm": 40,
        "height_cm": 25,
        **values,
    }


def availability(url: str, offer: dict[str, Any]) -> int:
    return sql(
        url,
        "SELECT available_seats FROM flight_cabins "
        "WHERE flight_id = :flight AND seat_class = :cabin",
        flight=offer["flight_id"],
        cabin=offer["seat_class"],
    )[0][0]


def test_search_filters_local_dates_city_names_prices_and_pagination(client: TestClient) -> None:
    result = client.get(
        "/api/v1/flights",
        params={
            "destination": "los angeles",
            "origin": "San Francisco",
            "departure_date": "2026-11-09",
            "max_price_cents": 9000,
            "sort_by": "price",
        },
    )
    assert result.status_code == 200
    assert len(result.json()["offers"]) == 1
    assert result.json()["offers"][0]["unit_price_cents"] == 8900
    overnight = offers(client, "2026-11-15", "LHR")
    assert len(overnight) == 1
    assert overnight[0]["departure_local"].startswith("2026-11-15")
    assert overnight[0]["arrival_local"].startswith("2026-11-16")
    first = client.get("/api/v1/flights", params={"limit": 1, "sort_by": "price"}).json()
    second = client.get(
        "/api/v1/flights", params={"limit": 1, "offset": 1, "sort_by": "price"}
    ).json()
    assert first["has_more"] is True
    assert first["offers"] != second["offers"]
    assert (
        client.get(
            "/api/v1/flights", params={"min_price_cents": 200, "max_price_cents": 100}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/flights", params={"departure_date": "invalid"}).status_code == 422
    assert (
        client.get("/api/v1/flights", params={"destination": "Unknown City"}).json()["offers"] == []
    )


def test_persistence_between_callers_instances_and_idempotent_retries(
    client: TestClient, postgres_url: str
) -> None:
    offer = offers(client)[0]
    before = availability(postgres_url, offer)
    request = payload(offer)
    first = client.post("/api/v1/bookings", json=request)
    assert first.status_code == 201, first.text
    record = first.json()
    assert record["flight"]["departure_local"] == offer["departure_local"]
    assert record["flight"]["arrival_local"] == offer["arrival_local"]
    assert record["flight"]["origin_timezone"] == "America/Los_Angeles"
    assert record["flight"]["departure_local"] != record["flight"]["departure_at"]
    assert client.post("/api/v1/bookings", json=request).json() == record
    assert client.post(f"{TOOLS}/book_flight", json=request).json() == record
    with TestClient(create_app(settings(postgres_url)), headers=HEADERS) as next_caller:
        retrieved = next_caller.post(
            f"{TOOLS}/get_booking", json={"reference": record["reference"].lower()}
        )
        assert retrieved.status_code == 200
        assert retrieved.json() == record
        assert next_caller.get("/api/v1/bookings").json()[0]["reference"] == record["reference"]
    duplicate = client.post("/api/v1/bookings", json={**request, "idempotency_key": str(uuid4())})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "passenger_already_booked"
    conflict = client.post("/api/v1/bookings", json={**request, "caller_id": "different"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert availability(postgres_url, offer) == before - 1
    assert sql(postgres_url, "SELECT count(*) FROM bookings")[0][0] == 1


def test_week_search_is_bounded_sorted_and_inclusive(client: TestClient) -> None:
    params = {
        "origin": "SFO",
        "destination": "JFK",
        "departure_date_from": "2026-11-10",
        "departure_date_to": "2026-11-12",
        "seat_class": "economy",
        "sort_by": "price",
        "limit": 200,
    }
    response = client.post(f"{TOOLS}/search_flights", json=params)
    assert response.status_code == 200, response.text
    found = response.json()["offers"]
    assert {o["departure_local"][:10] for o in found} == {"2026-11-10", "2026-11-11", "2026-11-12"}
    assert [o["unit_price_cents"] for o in found] == sorted(o["unit_price_cents"] for o in found)
    next_flight = client.get(
        "/api/v1/flights", params={"origin": "SFO", "destination": "JFK", "sort_by": "departure"}
    ).json()["offers"][0]
    assert next_flight["departure_local"].startswith("2026-11-09")
    for invalid in [
        {**params, "departure_date": "2026-11-11"},
        {**params, "departure_date_from": "2026-11-13"},
    ]:
        assert client.post(f"{TOOLS}/search_flights", json=invalid).status_code == 422


def test_preference_extension_preserves_pre_upgrade_idempotency_receipts(
    client: TestClient, postgres_url: str
) -> None:
    request = payload(offers(client)[0])
    response = client.post("/api/v1/bookings", json=request)
    assert response.status_code == 201
    legacy_response = response.json()
    for passenger in legacy_response["passengers"]:
        passenger.pop("seat_preference")
        passenger.pop("seat_preference_status")
    legacy_hash = hashlib.sha256(
        json.dumps(
            {"operation": "book", "request": request}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    sql(
        postgres_url,
        "UPDATE api_operations SET request_hash=:hash, response=CAST(:response AS jsonb) "
        "WHERE idempotency_key=:key",
        hash=legacy_hash,
        response=json.dumps(legacy_response),
        key=request["idempotency_key"],
    )
    retry = client.post("/api/v1/bookings", json=request)
    assert retry.status_code == 201, retry.text
    assert retry.json()["reference"] == legacy_response["reference"]
    assert retry.json()["passengers"][0]["seat_preference_status"] == "not_requested"
    assert sql(postgres_url, "SELECT count(*) FROM bookings")[0][0] == 1


@pytest.mark.parametrize("preference", ["window", "aisle", "extra_legroom"])
def test_seat_preferences_persist_across_calls_and_rescheduling(
    client: TestClient, postgres_url: str, preference: str
) -> None:
    offer = offers(client)[0]
    request = payload(offer)
    request["passengers"][0]["seat_preference"] = preference
    response = client.post(f"{TOOLS}/book_flight", json=request)
    assert response.status_code == 200, response.text
    booking = response.json()
    passenger = booking["passengers"][0]
    assert passenger["seat_preference"] == preference
    assert passenger["seat_preference_status"] == "requested"
    assert "seat_number" not in passenger
    with TestClient(create_app(settings(postgres_url)), headers=HEADERS) as next_caller:
        saved = next_caller.get(f"/api/v1/bookings/{booking['reference']}").json()
        assert saved["passengers"] == booking["passengers"]
        changed = next_caller.post(
            f"/api/v1/bookings/{booking['reference']}/reschedule",
            json=replacement(offers(next_caller, "2026-11-10")[0]),
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["passengers"] == booking["passengers"]


@pytest.mark.parametrize("status", ["scheduled", "cancelled", "departed", "arrived"])
def test_flight_information_is_independent_of_availability(
    client: TestClient, postgres_url: str, status: str
) -> None:
    offer = offers(client, destination="JFK")[0]
    sql(
        postgres_url,
        "UPDATE flights SET status=:status, gate='B17' WHERE id=:id",
        status=status,
        id=offer["flight_id"],
    )
    sql(
        postgres_url,
        "UPDATE flight_cabins SET available_seats=0 WHERE flight_id=:id",
        id=offer["flight_id"],
    )
    query = {"flight_number": offer["flight_number"].lower(), "departure_date": "2026-11-09"}
    result = client.post(f"{TOOLS}/get_flight_information", json=query)
    assert result.status_code == 200, result.text
    info = result.json()["flights"][0]
    assert info["flight_id"] == offer["flight_id"]
    assert info["status"] == status and info["gate"] == "B17"
    assert info["departure_local"] == offer["departure_local"]
    assert info["information_mode"] == "fictional_database"
    assert client.get("/api/v1/flights/information", params=query).json() == result.json()
    assert client.post(
        f"{TOOLS}/get_flight_information", json={**query, "flight_number": "NONE"}
    ).json() == {"flights": []}


def test_concurrent_last_seat_cannot_be_oversold(client: TestClient, postgres_url: str) -> None:
    offer = offers(client)[0]
    sql(
        postgres_url,
        "UPDATE flight_cabins SET available_seats = 1 "
        "WHERE flight_id = :flight AND seat_class = :cabin",
        flight=offer["flight_id"],
        cabin=offer["seat_class"],
    )
    requests = [payload(offer, f"racer-{index}") for index in range(12)]
    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(
            executor.map(lambda data: client.post("/api/v1/bookings", json=data), requests)
        )
    assert sorted(response.status_code for response in responses) == [201] + [409] * 11
    assert availability(postgres_url, offer) == 0
    assert sql(postgres_url, "SELECT count(*) FROM bookings")[0][0] == 1
    assert sql(postgres_url, "SELECT count(*) FROM passenger_reservations")[0][0] == 1
    assert sql(postgres_url, "SELECT count(*) FROM api_operations")[0][0] == 1


def test_concurrent_webhook_retries_make_one_booking(client: TestClient, postgres_url: str) -> None:
    offer = offers(client)[0]
    before = availability(postgres_url, offer)
    request = payload(offer)
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(
            executor.map(lambda _: client.post(f"{TOOLS}/book_flight", json=request), range(8))
        )
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["reference"] for response in responses}) == 1
    assert availability(postgres_url, offer) == before - 1
    assert sql(postgres_url, "SELECT count(*) FROM booking_events")[0][0] == 1


def test_cancel_releases_once_and_refunds_recorded_value(
    client: TestClient, postgres_url: str
) -> None:
    offer = offers(client, tier="flexible")[0]
    before = availability(postgres_url, offer)
    booking = book(client, offer)
    sql(
        postgres_url,
        "UPDATE flight_fares SET price_cents = 99999 "
        "WHERE flight_id = :flight AND seat_class = :cabin AND fare_tier = :tier",
        flight=offer["flight_id"],
        cabin=offer["seat_class"],
        tier=offer["fare_tier"],
    )
    path = f"/api/v1/bookings/{booking['reference']}/cancel"
    cancelled = client.post(path, json=action())
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["total_refunded_cents"] == booking["ticket_total_cents"]
    again = client.post(path, json=action())
    assert len(again.json()["events"]) == 2
    assert availability(postgres_url, offer) == before
    assert sql(postgres_url, "SELECT count(*) FROM passenger_reservations")[0][0] == 0
    assert client.get(f"/api/v1/bookings/{booking['id']}").json()["status"] == "cancelled"


def test_reschedule_updates_both_inventories_and_keeps_reference(
    client: TestClient, postgres_url: str
) -> None:
    original, target = offers(client)[0], offers(client, "2026-11-10")[0]
    old_before, new_before = (
        availability(postgres_url, original),
        availability(postgres_url, target),
    )
    booking = book(client, original)
    changed = client.post(
        f"/api/v1/bookings/{booking['reference']}/reschedule", json=replacement(target)
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["reference"] == booking["reference"]
    assert body["flight"]["id"] == target["flight_id"]
    assert body["ticket_total_cents"] == target["unit_price_cents"]
    assert (
        body["events"][-1]["charged_cents"]
        == 3000 + target["unit_price_cents"] - original["unit_price_cents"]
    )
    assert availability(postgres_url, original) == old_before
    assert availability(postgres_url, target) == new_before - 1
    assert (
        sql(postgres_url, "SELECT flight_id::text FROM passenger_reservations")[0][0]
        == target["flight_id"]
    )


def test_failed_reschedule_rolls_back_and_can_retry_same_key(
    client: TestClient, postgres_url: str
) -> None:
    original, target = offers(client)[0], offers(client, "2026-11-10")[0]
    booking = book(client, original)
    old_available = availability(postgres_url, original)
    sql(
        postgres_url,
        "UPDATE flight_cabins SET available_seats = 0 "
        "WHERE flight_id = :flight AND seat_class = :cabin",
        flight=target["flight_id"],
        cabin=target["seat_class"],
    )
    path = f"/api/v1/bookings/{booking['reference']}/reschedule"
    request = replacement(target)
    result = client.post(path, json=request)
    assert result.status_code == 409
    assert (
        client.get(f"/api/v1/bookings/{booking['reference']}").json()["flight"]["id"]
        == original["flight_id"]
    )
    assert availability(postgres_url, original) == old_available
    sql(
        postgres_url,
        "UPDATE flight_cabins SET available_seats = 1 "
        "WHERE flight_id = :flight AND seat_class = :cabin",
        flight=target["flight_id"],
        cabin=target["seat_class"],
    )
    assert client.post(path, json=request).status_code == 200


def test_duplicate_passenger_reschedule_rolls_back_both_flights(
    client: TestClient, postgres_url: str
) -> None:
    original, target = offers(client)[0], offers(client, "2026-11-10")[0]
    booking = book(client, original)
    book(client, target)
    before = (availability(postgres_url, original), availability(postgres_url, target))
    result = client.post(
        f"/api/v1/bookings/{booking['reference']}/reschedule", json=replacement(target)
    )
    assert result.status_code == 409
    assert (availability(postgres_url, original), availability(postgres_url, target)) == before
    assert (
        client.get(f"/api/v1/bookings/{booking['reference']}").json()["flight"]["id"]
        == original["flight_id"]
    )


def test_concurrent_opposite_reschedules_do_not_deadlock(
    client: TestClient, postgres_url: str
) -> None:
    original, target = offers(client)[0], offers(client, "2026-11-10")[0]
    first, second = book(client, original, "first"), book(client, target, "second")
    before = (availability(postgres_url, original), availability(postgres_url, target))
    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(
            client.post,
            f"/api/v1/bookings/{first['reference']}/reschedule",
            json=replacement(target),
        )
        b = executor.submit(
            client.post,
            f"/api/v1/bookings/{second['reference']}/reschedule",
            json=replacement(original),
        )
        assert a.result(timeout=10).status_code == 200
        assert b.result(timeout=10).status_code == 200
    assert (availability(postgres_url, original), availability(postgres_url, target)) == before


def test_baggage_policy_fees_pending_special_items_and_atomic_failure(client: TestClient) -> None:
    booking = book(client, offers(client, destination="YYZ", tier="basic")[0])
    path = f"/api/v1/bookings/{booking['reference']}/items"
    request = action(
        items=[
            bag(weight_kg=28, length_cm=70, width_cm=60, height_cm=40),
            {
                "passenger_id": "customer-1",
                "item_type": "mobility_aid",
                "description": "Folding wheelchair",
            },
            {"passenger_id": "customer-1", "item_type": "cabin_pet", "description": "Small cat"},
        ]
    )
    response = client.post(path, json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    items = {item["item_type"]: item for item in body["extras"]}
    assert items["checked_bag"]["price_cents"] == 31000
    assert items["mobility_aid"]["status"] == "pending_confirmation"
    assert items["mobility_aid"]["price_cents"] == 0
    assert items["cabin_pet"]["quoted_price_cents"] == 12500
    assert items["cabin_pet"]["status"] == "pending_confirmation"
    assert body["events"][-1]["charged_cents"] == 31000
    assert client.post(path, json=request).json() == body
    rejected = client.post(path, json=action(items=[bag(), bag(weight_kg=33)]))
    assert rejected.status_code == 422
    assert len(client.get(f"/api/v1/bookings/{booking['reference']}").json()["extras"]) == 3
    assert client.post(path, json=action(items=[bag(passenger="outsider")])).status_code == 422


def test_premium_economy_uses_purchased_tier_and_reprices_bags(client: TestClient) -> None:
    original = offers(client, destination="YYZ", seat_class="premium_economy")[0]
    booking = book(client, original)
    path = f"/api/v1/bookings/{booking['reference']}"
    added = client.post(path + "/items", json=action(items=[bag(), bag()]))
    assert added.status_code == 200
    assert sum(item["price_cents"] for item in added.json()["extras"]) == 6000
    target = offers(client, "2026-11-10", "YYZ", "premium_economy", "flexible")[0]
    changed = client.post(path + "/reschedule", json=replacement(target))
    assert changed.status_code == 200, changed.text
    assert sum(item["price_cents"] for item in changed.json()["extras"]) == 0
    assert changed.json()["events"][-1]["details"]["baggage_adjustment_cents"] == -6000


def test_standard_bag_registration_uses_included_allowance_once_across_requests(
    client: TestClient,
) -> None:
    booking = book(client, offers(client, destination="JFK")[0])
    path = f"/api/v1/bookings/{booking['reference']}"
    first = client.post(path + "/items", json=action(items=[bag()]))
    assert first.status_code == 200
    assert first.json()["extras"][0]["price_cents"] == 0
    request = action(items=[bag()])
    second = client.post(path + "/items", json=request)
    assert second.status_code == 200
    saved = second.json()
    assert [item["price_cents"] for item in saved["extras"]] == [0, 3500]
    assert saved["events"][-1]["charged_cents"] == 3500
    assert saved["total_charged_cents"] == booking["ticket_total_cents"] + 3500
    assert client.post(path + "/items", json=request).json() == saved
    target = offers(client, "2026-11-10", "JFK")[0]
    changed = client.post(path + "/reschedule", json=replacement(target))
    assert changed.status_code == 200
    assert [item["price_cents"] for item in changed.json()["extras"]] == [0, 3500]
    assert changed.json()["events"][-1]["details"]["baggage_adjustment_cents"] == 0


def test_fare_restrictions_quote_changes_and_group_uniqueness(
    client: TestClient, postgres_url: str
) -> None:
    original = offers(client, tier="basic")[0]
    stale = payload(original)
    stale["expected_unit_price_cents"] += 1
    result = client.post("/api/v1/bookings", json=stale)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "fare_price_changed"
    duplicate = payload(original)
    duplicate["passengers"] *= 2
    assert client.post("/api/v1/bookings", json=duplicate).status_code == 422
    group = payload(original)
    group["passengers"].append({"passenger_id": "second", "full_name": "Second Passenger"})
    before = availability(postgres_url, original)
    booked = client.post("/api/v1/bookings", json=group)
    assert booked.status_code == 201
    assert booked.json()["ticket_total_cents"] == original["unit_price_cents"] * 2
    assert availability(postgres_url, original) == before - 2
    target = offers(client, "2026-11-10", tier="basic")[0]
    assert (
        client.post(
            f"/api/v1/bookings/{booked.json()['reference']}/reschedule", json=replacement(target)
        ).status_code
        == 409
    )


def test_grace_period_and_nonrefundable_tax_review(client: TestClient) -> None:
    standard = book(client, offers(client)[0])
    cancelled = client.post(f"/api/v1/bookings/{standard['reference']}/cancel", json=action())
    assert cancelled.status_code == 200
    settlement = cancelled.json()["events"][-1]["details"]
    assert settlement["reason"] == "travel_credit_pending_tax_breakdown"
    assert settlement["review_required"] is True
    assert cancelled.json()["total_credit_cents"] == 0
    future_basic = book(client, offers(client, "2026-11-15", tier="basic")[0], "later")
    refunded = client.post(f"/api/v1/bookings/{future_basic['reference']}/cancel", json=action())
    assert refunded.status_code == 200
    assert refunded.json()["events"][-1]["details"]["reason"] == "grace_period"
    assert refunded.json()["total_refunded_cents"] == future_basic["ticket_total_cents"]


def test_six_webhook_tools_share_rest_database(client: TestClient) -> None:
    result = client.post(
        f"{TOOLS}/search_flights",
        json={
            "origin": "SFO",
            "destination": "LAX",
            "departure_date": "2026-11-09",
            "seat_class": "economy",
            "fare_tier": "standard",
        },
    )
    assert result.status_code == 200
    offer = result.json()["offers"][0]
    made = client.post(f"{TOOLS}/book_flight", json=payload(offer))
    assert made.status_code == 200, made.text
    reference = made.json()["reference"]
    assert client.get(f"/api/v1/bookings/{reference}").status_code == 200
    assert (
        client.post(f"{TOOLS}/get_booking", json={"reference": reference}).json()["reference"]
        == reference
    )
    assert (
        client.post(
            f"{TOOLS}/add_booking_items", json=action(reference=reference, items=[bag()])
        ).status_code
        == 200
    )
    target = offers(client, "2026-11-10")[0]
    assert (
        client.post(
            f"{TOOLS}/reschedule_booking", json={"reference": reference, **replacement(target)}
        ).status_code
        == 200
    )
    cancelled = client.post(f"{TOOLS}/cancel_booking", json=action(reference=reference))
    assert cancelled.status_code == 200
    assert client.get(f"/api/v1/bookings/{reference}").json()["status"] == "cancelled"


def test_agent_authentication_and_unknown_references(client: TestClient) -> None:
    assert client.get("/api/v1/flights", headers={"X-Agent-Api-Key": "wrong"}).status_code == 401
    assert (
        client.post(
            f"{TOOLS}/search_flights", json={}, headers={"X-Agent-Api-Key": "wrong"}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/bookings/UNKNOWN").status_code == 404
    assert client.get("/api/v1/bookings/" + "A" * 200).status_code == 422
    assert client.post("/api/v1/bookings", json={}).status_code == 422
    production = Settings(_env_file=None, app_env="production", agent_api_key=None)
    with TestClient(create_app(production)) as protected:
        assert protected.get("/api/v1/flights").status_code == 503


def test_booking_survives_application_shutdown_and_restart(postgres_url: str) -> None:
    asyncio.run(seed_dataset(postgres_url, load_dataset()))
    with TestClient(create_app(settings(postgres_url)), headers=HEADERS) as first:
        booking = book(first, offers(first)[0])
    with TestClient(create_app(settings(postgres_url)), headers=HEADERS) as second:
        response = second.get(f"/api/v1/bookings/{booking['reference']}")
        assert response.status_code == 200
        assert response.json() == booking


def test_concurrent_cancellations_release_seats_only_once(
    client: TestClient, postgres_url: str
) -> None:
    offer = offers(client, tier="flexible")[0]
    before = availability(postgres_url, offer)
    booking = book(client, offer)
    path = f"/api/v1/bookings/{booking['reference']}/cancel"
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: client.post(path, json=action()), range(6)))
    assert all(result.status_code == 200 for result in results)
    assert all(len(result.json()["events"]) == 2 for result in results)
    assert availability(postgres_url, offer) == before
    assert (
        sql(postgres_url, "SELECT count(*) FROM booking_events WHERE action = 'cancelled'")[0][0]
        == 1
    )


def test_existing_booking_uses_its_persisted_policy_snapshot(client: TestClient) -> None:
    offer = offers(client, tier="basic")[0]
    existing = book(client, offer)
    snapshot = deepcopy(client.app.state.policies.snapshot)
    snapshot["rules"]["baggage.additional_piece_fees"]["additional_piece_fees"]["domestic"][
        "first_additional"
    ] = 150
    from airline_api.modules.bookings.policies import PolicyCatalog

    client.app.state.policies = PolicyCatalog(snapshot)
    old = client.post(f"/api/v1/bookings/{existing['reference']}/items", json=action(items=[bag()]))
    assert old.status_code == 200
    assert old.json()["extras"][0]["price_cents"] == 3500
    new = book(client, offer, "new-customer")
    added = client.post(
        f"/api/v1/bookings/{new['reference']}/items", json=action(items=[bag("new-customer")])
    )
    assert added.status_code == 200
    assert added.json()["extras"][0]["price_cents"] == 15000


def test_airline_cancellation_rebooking_waives_basic_restriction_and_price_difference(
    client: TestClient, postgres_url: str
) -> None:
    original = offers(client, tier="basic")[0]
    target = offers(client, "2026-11-10", tier="basic")[0]
    booking = book(client, original)
    sql(
        postgres_url,
        "UPDATE flights SET status = 'cancelled' WHERE id = :flight",
        flight=original["flight_id"],
    )
    result = client.post(
        f"/api/v1/bookings/{booking['reference']}/reschedule", json=replacement(target)
    )
    assert result.status_code == 200, result.text
    assert result.json()["flight"]["id"] == target["flight_id"]
    assert result.json()["ticket_total_cents"] == original["unit_price_cents"]
    assert result.json()["events"][-1]["charged_cents"] == 0
    assert result.json()["events"][-1]["details"]["airline_disruption"] is True


def test_readiness_is_authenticated_and_independent_of_broken_search(client, monkeypatch):
    from airline_api.modules.bookings.service import BookingService

    async def broken_search(*args):
        raise RuntimeError("Injected application defect")

    monkeypatch.setattr(BookingService, "search", broken_search)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "business_time": "2026-11-05T12:00:00+00:00"}
    assert client.get("/ready", headers={"X-Agent-Api-Key": "wrong"}).status_code == 401
