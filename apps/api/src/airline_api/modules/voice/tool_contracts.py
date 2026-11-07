"""Export backend webhook contracts for configuring ElevenLabs tools."""

import json
from typing import Any

from pydantic import BaseModel

from airline_api.modules.bookings.schemas import (
    AddBookingItemsTool,
    BookFlight,
    BookingReference,
    CancelBookingTool,
    FlightInformationQuery,
    FlightSearch,
    RescheduleBookingTool,
)

TOOL_MODELS: list[tuple[str, type[BaseModel], str]] = [
    (
        "get_flight_information",
        FlightInformationQuery,
        "Get fictional gate, local times, and status by flight number and local departure date. "
        "Includes cancelled, departed, sold-out, and arrived flights; does not change bookings.",
    ),
    (
        "search_flights",
        FlightSearch,
        "Find available flights and current prices before offering or booking travel.",
    ),
    (
        "book_flight",
        BookFlight,
        "Reserve a confirmed flight quote. Reuse action keys and stable passenger IDs.",
    ),
    (
        "get_booking",
        BookingReference,
        "Retrieve saved booking details and changes by booking reference.",
    ),
    (
        "cancel_booking",
        CancelBookingTool,
        "Cancel confirmed travel and release seats; read the saved settlement result.",
    ),
    (
        "reschedule_booking",
        RescheduleBookingTool,
        "Search and confirm a replacement, then reschedule on the same route.",
    ),
    (
        "add_booking_items",
        AddBookingItemsTool,
        "Add checked bags or request special items; read each item's confirmation status.",
    ),
]


def build_tool_contracts() -> dict[str, Any]:
    return {
        "format": "airline-voice-webhook-contracts-v1",
        "authentication": {
            "header": "X-Agent-Api-Key",
            "secret_environment_variable": "AGENT_API_KEY",
        },
        "tools": [
            {
                "name": name,
                "description": description,
                "method": "POST",
                "path": f"/api/v1/voice/webhooks/elevenlabs/{name}",
                "request_schema": model.model_json_schema(),
            }
            for name, model, description in TOOL_MODELS
        ],
    }


if __name__ == "__main__":
    print(json.dumps(build_tool_contracts(), indent=2))
