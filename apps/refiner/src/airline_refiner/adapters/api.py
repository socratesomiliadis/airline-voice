"""Airline fixture lifecycle and provider REST access; no credentials in artifacts."""

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from airline_refiner.errors import RefinementError
from airline_refiner.models import Scenario


async def request(
    client: httpx.AsyncClient, method: str, path: str, **kwargs: Any
) -> dict[str, Any] | list[Any]:
    try:
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        data: dict[str, Any] | list[Any] = response.json()
        if not isinstance(data, (dict, list)):
            raise ValueError("Expected a JSON object or array")
        return data
    except httpx.HTTPStatusError as error:
        raise RefinementError(
            f"{method} {path} failed (HTTP {error.response.status_code})"
        ) from None
    except (httpx.RequestError, ValueError):
        raise RefinementError(f"{method} {path} failed (transport or invalid JSON)") from None


class AirlineAPI:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def ready(self, timeout_seconds: float) -> None:
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    try:
                        await request(self.client, "GET", "health")
                        # Liveness alone does not establish DB, migration or auth readiness.
                        result = await request(
                            self.client, "GET", "api/v1/flights", params={"limit": 1}
                        )
                        if not isinstance(result, dict) or not result.get("offers"):
                            raise RefinementError("Flight readiness requires seeded inventory")
                        return
                    except RefinementError:
                        await asyncio.sleep(1)
        except TimeoutError:
            raise RefinementError("Airline API did not become ready before timeout") from None

    async def prepare(self, scenario: Scenario, caller: str) -> dict[str, Any]:
        identity = {"passenger_id": caller, "full_name": "Jordan Taylor"}
        fixture: dict[str, Any] = {"passenger": identity}
        if scenario.setup is None:
            return fixture
        result = await request(
            self.client,
            "GET",
            "api/v1/flights",
            params={**scenario.setup.model_dump(), "passengers": 1, "limit": 1},
        )
        if not isinstance(result, dict) or not result.get("offers"):
            raise RefinementError(f"No inventory for scenario fixture {scenario.id}")
        offer = result["offers"][0]
        booking = await request(
            self.client,
            "POST",
            "api/v1/bookings",
            json={
                "flight_id": offer["flight_id"],
                "seat_class": offer["seat_class"],
                "fare_tier": offer["fare_tier"],
                "expected_unit_price_cents": offer["unit_price_cents"],
                "passengers": [identity],
                "caller_id": caller,
                "idempotency_key": caller + "-setup",
            },
        )
        fixture["booking"] = booking
        return fixture

    async def capture(self, fixture: dict[str, Any], conversation_id: str | None) -> list[Any]:
        bookings: list[Any] = []
        if "booking" in fixture:
            reference = quote(fixture["booking"]["reference"], safe="")
            bookings.append(await request(self.client, "GET", f"api/v1/bookings/{reference}"))
        if conversation_id:
            result = await request(
                self.client,
                "GET",
                "api/v1/bookings",
                params={"caller_id": conversation_id, "limit": 200},
            )
            if not isinstance(result, list):
                raise RefinementError("Booking list returned an invalid response")
            known = {booking["reference"] for booking in bookings}
            bookings.extend(booking for booking in result if booking["reference"] not in known)
        return bookings

    async def cleanup(
        self, fixture: dict[str, Any], conversation_id: str | None, caller: str
    ) -> None:
        bookings = await self.capture(fixture, conversation_id)
        # Also find a setup booking if its POST succeeded but the response was lost.
        setup_bookings = await request(
            self.client, "GET", "api/v1/bookings", params={"caller_id": caller, "limit": 200}
        )
        if isinstance(setup_bookings, list):
            known = {booking["reference"] for booking in bookings}
            bookings.extend(
                booking for booking in setup_bookings if booking["reference"] not in known
            )
        for booking in bookings:
            if booking["status"] != "cancelled":
                reference = quote(booking["reference"], safe="")
                await request(
                    self.client,
                    "POST",
                    f"api/v1/bookings/{reference}/cancel",
                    json={"caller_id": caller, "idempotency_key": caller + "-" + reference},
                )
