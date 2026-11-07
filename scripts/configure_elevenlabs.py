"""Sync this project's private ElevenLabs agent, policies and webhook tools.

Run from the repository root. Credentials are read from .env/environment only.
Resource IDs and policy hashes are recorded so subsequent runs update our resources.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from airline_api.modules.voice.tool_contracts import build_tool_contracts
from dotenv import dotenv_values
from elevenlabs import ElevenLabs, ToolRequestModel
from elevenlabs.core.api_error import ApiError

ROOT = Path(__file__).resolve().parents[1]
STATE_DIRECTORY = ROOT / ".local/elevenlabs"
GREETING = (
    "Hi, I’m Avery, the AI assistant for Airline Voice Demo. "
    "I can help with our simulated flights, bookings, baggage, and travel policies. "
    "How can I help you today?"
)
DESCRIPTIONS = {
    "origin": "Origin IATA airport code or exact city name; omit if unspecified.",
    "reference": "Saved booking reference (10 characters) or booking UUID.",
    "flight_id": "Exact flight UUID returned by the latest search, never a flight number.",
    "seat_class": "Cabin returned by search; distinct from fare tier.",
    "fare_tier": "Purchased fare tier returned by search; determines policy and price.",
    "expected_unit_price_cents": "Exact per-passenger USD-cent fare from the selected offer.",
    "passenger_id": "Stable passenger/customer ID; reuse across calls and bookings.",
    "full_name": "Passenger full name supplied by the customer.",
    "idempotency_key": (
        "Unique key, 8–128 characters: current conversation ID, action and counter. "
        "Reuse the exact key and payload only for retries of the same confirmed action."
    ),
    "passengers": "Passenger count 1–9 for search, or all passengers to book with stable IDs.",
    "sort_by": "Sort by departure or price.",
    "departure_date_from": "Inclusive first departure-airport local date, YYYY-MM-DD.",
    "departure_date_to": "Inclusive last departure-airport local date, YYYY-MM-DD.",
    "flight_number": "Flight number supplied by the customer, for example DEMO301.",
    "limit": "Maximum offers to return, 1–200. Use 6 initially to keep responses concise.",
    "offset": "Pagination offset, nonnegative integer; omit for first results.",
    "items": (
        "New physical items assigned to booked passengers; 1–20 per request. For checked bags, "
        "register every unrecorded physical bag, including fare-included bags, not just paid "
        "additional pieces. The backend applies the allowance. Subtract already confirmed "
        "checked-bag extras from the customer's desired total; never register them twice."
    ),
    "item_type": "Item category; special items are requests subject to confirmation.",
    "weight_kg": "Positive weight in kilograms. Required for checked_bag.",
    "length_cm": "Positive length in centimeters. Required for checked_bag.",
    "width_cm": "Positive width in centimeters. Required for checked_bag.",
    "height_cm": "Positive height in centimeters. Required for checked_bag.",
    "description": "Customer-supplied item details, maximum 1000 characters.",
}


def provider_schema(schema: dict[str, Any], defs: dict[str, Any], name: str = "") -> dict:
    """Resolve Pydantic schemas into ElevenLabs' supported parameter schema dialect."""
    schema = dict(schema)
    if "$ref" in schema:
        schema = {**defs[schema.pop("$ref").split("/")[-1]], **schema}
    if "anyOf" in schema:
        # Optional fields are omitted, not null; Decimal measurements accept numbers.
        choices = [s for s in schema.pop("anyOf") if s.get("type") != "null"]
        return provider_schema({**choices[0], **schema}, defs, name)
    if name == "caller_id":
        return {"type": "string", "dynamic_variable": "system__conversation_id"}
    result = {
        "type": schema["type"],
        "description": DESCRIPTIONS.get(name, schema.get("description", name or "Tool request")),
    }
    if "enum" in schema:
        result["enum"] = schema["enum"]
    if schema["type"] == "object":
        result["properties"] = {
            key: provider_schema(value, defs, key)
            for key, value in schema.get("properties", {}).items()
        }
        result["required"] = schema.get("required", [])
    elif schema["type"] == "array":
        result["items"] = provider_schema(schema["items"], defs, name + " entry")
    return result


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path)


def load_state(path: Path, agent_id: str | None) -> dict:
    state = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(state, dict):
        raise ValueError("State file must contain a JSON object")
    if agent_id and state.get("agent_id", agent_id) != agent_id:
        raise ValueError("State file belongs to another agent; choose a different --state-file")
    return state


def main() -> None:
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default=env.get("PUBLIC_API_BASE_URL"))
    agents = parser.add_mutually_exclusive_group()
    agents.add_argument("--agent-id", default=env.get("ELEVENLABS_AGENT_ID"))
    agents.add_argument("--create-agent", metavar="NAME", help="Create or resume a private agent")
    parser.add_argument("--state-file", type=Path, help="Local resumable resource manifest")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=ROOT / "prompts/agent/system.md",
        help="System prompt to publish (use a separate private agent for recorded baselines)",
    )
    args = parser.parse_args()
    if not env.get("ELEVENLABS_API_KEY") or not env.get("AGENT_API_KEY"):
        parser.error("Set ELEVENLABS_API_KEY and AGENT_API_KEY in .env")
    if not args.create_agent and not args.agent_id:
        parser.error("Use --create-agent NAME, --agent-id ID, or set ELEVENLABS_AGENT_ID")
    identity = (
        "new-" + hashlib.sha256(args.create_agent.encode()).hexdigest()[:16]
        if args.create_agent
        else args.agent_id
    )
    state_path = args.state_file or STATE_DIRECTORY / f"{identity}.json"
    try:
        state = load_state(state_path, None if args.create_agent else args.agent_id)
    except ValueError as error:
        parser.error(str(error))
    base = (args.api_base_url or "").rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query:
        parser.error("--api-base-url / PUBLIC_API_BASE_URL must be a public HTTPS base URL")

    # Verify the intended destination before sending secret-bearing webhook requests.
    health = httpx.get(base + "/health", timeout=30)
    health.raise_for_status()
    response = httpx.post(
        base + "/api/v1/voice/webhooks/elevenlabs/search_flights",
        headers={"X-Agent-Api-Key": env["AGENT_API_KEY"]},
        json={"limit": 1},
        timeout=30,
    )
    response.raise_for_status()
    if not response.json().get("offers"):
        parser.error("Public API has no bookable flights; migrate, seed, and set SIMULATION_NOW")
    client = ElevenLabs(api_key=env["ELEVENLABS_API_KEY"])
    api = client.conversational_ai
    prompt = args.prompt_file.read_text().strip()
    if not prompt:
        parser.error("System prompt cannot be empty")
    if args.create_agent:
        if not state.get("agent_id"):
            created = api.agents.create(
                name=args.create_agent,
                enable_versioning=True,
                conversation_config={
                    "agent": {
                        "first_message": GREETING,
                        "prompt": {"prompt": prompt},
                    }
                },
                platform_settings={"auth": {"enable_auth": True}},
            )
            state["agent_id"] = created.agent_id
            save_state(state_path, state)
        args.agent_id = state["agent_id"]
        if args.state_file is None:
            # The name-based creation receipt points to the canonical per-agent state.
            # Later invocations with ELEVENLABS_AGENT_ID must reuse the same tools/secrets.
            state_path = STATE_DIRECTORY / f"{args.agent_id}.json"
            state = load_state(state_path, args.agent_id)
            state.setdefault("agent_id", args.agent_id)
            save_state(state_path, state)
    agent = api.agents.get(args.agent_id)
    state.update(agent_id=args.agent_id, branch_id=agent.branch_id, api_base_url=base)
    state.setdefault("tools", {})
    state.setdefault("knowledge_base", {})
    secret_name = f"airline_voice_{args.agent_id}"
    if not state.get("secret_id"):
        secret = api.secrets.create(name=secret_name, value=env["AGENT_API_KEY"])
        state["secret_id"] = secret.secret_id
        save_state(state_path, state)
    else:
        api.secrets.update(state["secret_id"], name=secret_name, value=env["AGENT_API_KEY"])

    for tool in build_tool_contracts()["tools"]:
        config = {
            "type": "webhook",
            "name": tool["name"],
            "description": tool["description"],
            "response_timeout_secs": 20,
            "pre_tool_speech": "off",
            "interruption_mode": (
                "allow"
                if tool["name"] in {"search_flights", "get_booking"}
                else "disable_during_tool"
            ),
            "tool_error_handling_mode": "passthrough",
            "execution_mode": "immediate",
            "follow_redirects": False,
            "api_schema": {
                "url": base + tool["path"],
                "method": "POST",
                "content_type": "application/json",
                "request_headers": {"X-Agent-Api-Key": {"secret_id": state["secret_id"]}},
                "request_body_schema": provider_schema(
                    tool["request_schema"], tool["request_schema"].get("$defs", {})
                ),
            },
        }
        request = ToolRequestModel.model_validate({"tool_config": config})
        tool_id = state["tools"].get(tool["name"])
        saved = (
            api.tools.update(tool_id, request=request)
            if tool_id
            else api.tools.create(request=request)
        )
        state["tools"][tool["name"]] = saved.id
        save_state(state_path, state)
        print("Configured tool:", tool["name"])

    locators = []
    for source in sorted((ROOT / "knowledge").glob("*.json")):
        text = source.read_text()
        digest = hashlib.sha256(text.encode()).hexdigest()
        record = state["knowledge_base"].get(source.name)
        if not record or record.get("sha256") != digest:
            # New revision: existing conversations can retain the previous document.
            document = api.knowledge_base.documents.create_from_text(name=source.name, text=text)
            record = {"id": document.id, "type": "text", "name": source.name, "sha256": digest}
            state["knowledge_base"][source.name] = record
            save_state(state_path, state)
        locators.append({key: record[key] for key in ("id", "type", "name")})

    saved = api.agents.update(
        args.agent_id,
        branch_id=agent.branch_id,
        conversation_config={
            "agent": {
                "first_message": GREETING,
                "prompt": {
                    "prompt": prompt,
                    "tool_ids": list(state["tools"].values()),
                    "knowledge_base": [{**x, "usage_mode": "auto"} for x in locators],
                    "enable_parallel_tool_calls": False,
                    "max_tokens": 1000,
                    "built_in_tools": {
                        "end_call": {
                            "type": "system",
                            "name": "end_call",
                            "params": {"system_tool_type": "end_call"},
                        },
                    },
                },
            },
        },
        platform_settings={"auth": {"enable_auth": True}},
        version_description="Configure fictional airline policies and authenticated booking tools",
    )
    state["version_id"] = saved.version_id
    save_state(state_path, state)
    assert saved.platform_settings.auth.enable_auth
    assert set(saved.conversation_config.agent.prompt.tool_ids) == set(state["tools"].values())
    print("Published private agent:", saved.agent_id)
    print("Knowledge documents:", len(locators))
    print("API base URL:", base)
    print("Local resource state:", state_path)
    print("Set ELEVENLABS_AGENT_ID=" + saved.agent_id + " in .env before running refinement.")


if __name__ == "__main__":
    try:
        main()
    except ApiError as error:
        # Provider errors can echo inputs. Do not dump credential-bearing requests.
        raise SystemExit(f"ElevenLabs rejected the request (HTTP {error.status_code}).") from None
