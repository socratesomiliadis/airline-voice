"""Airline fixture lifecycle and provider REST access; no credentials in artifacts."""

import asyncio
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from airline_refiner.errors import ApplicationError, RefinementError
from airline_refiner.models import Scenario
from airline_refiner.reference import DEFAULT_DATASET, selection_reference


async def send(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> httpx.Response:
    try:
        return await client.request(method, path, **kwargs)
    except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError):
        # An unhandled ASGI exception closes the connection after sending HTTP 500.
        # Pooled requests, including readiness probes, can race that close.
        if method != "GET" and not kwargs.get("json", {}).get("idempotency_key"):
            raise
        return await client.request(method, path, **kwargs)


async def request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    diagnose_application: bool = False,
    **kwargs: Any,
) -> dict[str, Any] | list[Any]:
    # Only retry reads and mutations carrying the service's durable idempotency key.
    # Authentication, transport failures and unavailable dependencies remain infrastructure errors.
    try:
        response = await send(client, method, path, **kwargs)
        replay_safe = method == "GET" or bool(kwargs.get("json", {}).get("idempotency_key"))
        if response.status_code >= 500 and replay_safe and diagnose_application:
            repeated = await send(client, method, path, **kwargs)
            if repeated.status_code == response.status_code:
                health = await send(client, "GET", "health")
                inventory = await send(client, "GET", "ready")
                if (
                    health.is_success
                    and inventory.is_success
                    and isinstance(inventory.json(), dict)
                    and inventory.json().get("status") == "ok"
                ):
                    raise ApplicationError(method, path, response.status_code)
            response = repeated
        response.raise_for_status()
        data: dict[str, Any] | list[Any] = response.json()
        if not isinstance(data, (dict, list)):
            raise ValueError("Expected a JSON object or array")
        return data
    except httpx.HTTPStatusError as error:
        raise RefinementError(
            f"{method} {path} failed (HTTP {error.response.status_code})"
        ) from None
    except (httpx.RequestError, ssl.SSLError) as error:
        raise RefinementError(
            f"{method} {path} failed (transport: {type(error).__name__})"
        ) from None
    except ValueError:
        raise RefinementError(f"{method} {path} failed (invalid JSON)") from None


class AirlineAPI:
    def __init__(self, client: httpx.AsyncClient, dataset_path: Path = DEFAULT_DATASET) -> None:
        self.client = client
        self.dataset_path = dataset_path

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        return await request(self.client, method, path, diagnose_application=True, **kwargs)

    async def ready(self, timeout_seconds: float) -> None:
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    try:
                        await self.request("GET", "health")
                        # Liveness alone does not establish DB, migration or auth readiness.
                        result = await self.request("GET", "ready")
                        if not isinstance(result, dict) or result.get("status") != "ok":
                            raise RefinementError("Flight readiness requires seeded inventory")
                        return
                    except RefinementError:
                        await asyncio.sleep(1)
        except TimeoutError:
            raise RefinementError("Airline API did not become ready before timeout") from None

    async def prepare(self, scenario: Scenario, caller: str) -> dict[str, Any]:
        identity = {"passenger_id": caller, "full_name": "Jordan Taylor"}
        fixture: dict[str, Any] = {"passenger": identity}
        readiness = await self.request("GET", "ready")
        if not isinstance(readiness, dict) or not readiness.get("business_time"):
            raise RefinementError("Readiness must supply the demonstration business time")
        fixture["business_time"] = readiness["business_time"]
        if scenario.assertions.selection:
            fixture["selection_reference"] = selection_reference(
                scenario, self.dataset_path, fixture["business_time"]
            )
        if scenario.setup is None:
            return fixture
        result = await self.request(
            "GET",
            "api/v1/flights",
            params={**scenario.setup.model_dump(), "passengers": 1, "limit": 1},
        )
        if not isinstance(result, dict) or not result.get("offers"):
            raise RefinementError(f"No inventory for scenario fixture {scenario.id}")
        offer = result["offers"][0]
        booking = await self.request(
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
            bookings.append(await self.request("GET", f"api/v1/bookings/{reference}"))
        if conversation_id:
            result = await self.request(
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
        setup_bookings = await self.request(
            "GET", "api/v1/bookings", params={"caller_id": caller, "limit": 200}
        )
        if isinstance(setup_bookings, list):
            known = {booking["reference"] for booking in bookings}
            bookings.extend(
                booking for booking in setup_bookings if booking["reference"] not in known
            )
        for booking in bookings:
            if booking["status"] != "cancelled":
                reference = quote(booking["reference"], safe="")
                await self.request(
                    "POST",
                    f"api/v1/bookings/{reference}/cancel",
                    json={"caller_id": caller, "idempotency_key": caller + "-" + reference},
                )
