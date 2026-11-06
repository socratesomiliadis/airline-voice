"""Provider-specific tool schemas must preserve our transactional API contracts."""

import json

from airline_api.modules.voice.tool_contracts import build_tool_contracts
from elevenlabs import ToolRequestModel

from scripts.configure_elevenlabs import provider_schema


def converted(name: str) -> dict:
    tool = next(t for t in build_tool_contracts()["tools"] if t["name"] == name)
    source = tool["request_schema"]
    return provider_schema(source, source.get("$defs", {}))


def test_provider_accepts_all_six_body_schemas() -> None:
    for tool in build_tool_contracts()["tools"]:
        schema = converted(tool["name"])
        request = ToolRequestModel.model_validate(
            {
                "tool_config": {
                    "type": "webhook",
                    "name": tool["name"],
                    "description": tool["description"],
                    "api_schema": {
                        "url": "https://example.com" + tool["path"],
                        "method": "POST",
                        "request_body_schema": schema,
                    },
                }
            }
        )
        body = request.model_dump(mode="json")["tool_config"]["api_schema"]["request_body_schema"]
        assert set(body["required"]) == set(tool["request_schema"].get("required", []))
        assert "$ref" not in json.dumps(body)
        assert "anyOf" not in json.dumps(body)


def test_identity_is_injected_and_nested_passengers_are_required() -> None:
    body = converted("book_flight")
    properties = body["properties"]
    assert properties["caller_id"] == {
        "type": "string",
        "dynamic_variable": "system__conversation_id",
    }
    assert set(properties["passengers"]["items"]["required"]) == {"passenger_id", "full_name"}
    assert properties["expected_unit_price_cents"]["type"] == "integer"
    assert "idempotency_key" in body["required"]


def test_optional_search_filters_and_numeric_baggage_measurements() -> None:
    search = converted("search_flights")
    assert search["required"] == []
    assert search["properties"]["departure_date"]["type"] == "string"
    assert search["properties"]["max_price_cents"]["type"] == "integer"
    item = converted("add_booking_items")["properties"]["items"]["items"]
    assert set(item["required"]) == {"passenger_id", "item_type"}
    for field in ("weight_kg", "length_cm", "width_cm", "height_cm"):
        assert item["properties"][field]["type"] == "number"
    assert "checked_bag" in item["properties"]["item_type"]["enum"]
