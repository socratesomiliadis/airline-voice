"""Provider-specific tool schemas must preserve our transactional API contracts."""

import json
from types import SimpleNamespace

import pytest
from airline_api.modules.voice.tool_contracts import build_tool_contracts
from elevenlabs import ToolRequestModel

from scripts.configure_elevenlabs import load_state, provider_schema, save_state


def converted(name: str) -> dict:
    tool = next(t for t in build_tool_contracts()["tools"] if t["name"] == name)
    source = tool["request_schema"]
    return provider_schema(source, source.get("$defs", {}))


def test_provider_accepts_all_body_schemas() -> None:
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


def test_resource_state_is_local_separate_per_agent_and_resumable(tmp_path) -> None:
    first, second = tmp_path / "one/state.json", tmp_path / "two/state.json"
    save_state(first, {"agent_id": "agent-one", "tools": {"search": "tool-one"}})
    save_state(second, {"agent_id": "agent-two"})
    assert load_state(first, "agent-one")["tools"] == {"search": "tool-one"}
    assert load_state(second, "agent-two") == {"agent_id": "agent-two"}
    assert load_state(tmp_path / "new.json", "new-agent") == {}
    with pytest.raises(ValueError, match="another agent"):
        load_state(first, "agent-two")


def test_fresh_account_creation_and_retry_do_not_inherit_another_agent(monkeypatch, tmp_path):
    from scripts import configure_elevenlabs as setup

    (tmp_path / "prompts/agent").mkdir(parents=True)
    (tmp_path / "prompts/agent/system.md").write_text("Fictional airline prompt")
    (tmp_path / "knowledge").mkdir()
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    monkeypatch.setattr(setup, "STATE_DIRECTORY", tmp_path / "local")
    for key, value in {
        "ELEVENLABS_API_KEY": "test-key",
        "AGENT_API_KEY": "test-secret",
        "ELEVENLABS_AGENT_ID": "another-existing-agent",
        "PUBLIC_API_BASE_URL": "https://example.test",
    }.items():
        monkeypatch.setenv(key, value)
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"offers": [{}]})
    monkeypatch.setattr(setup.httpx, "get", lambda *a, **k: response)
    monkeypatch.setattr(setup.httpx, "post", lambda *a, **k: response)
    created, fetched, updated = [], [], []

    def create(**kwargs):
        created.append(kwargs)
        return SimpleNamespace(agent_id="new-agent")

    def get(agent_id):
        fetched.append(agent_id)
        return SimpleNamespace(branch_id="new-branch")

    def update(agent_id, **kwargs):
        updated.append(agent_id)
        return SimpleNamespace(
            agent_id=agent_id,
            version_id="new-version",
            platform_settings=SimpleNamespace(auth=SimpleNamespace(enable_auth=True)),
            conversation_config=SimpleNamespace(
                agent=SimpleNamespace(
                    prompt=SimpleNamespace(
                        tool_ids=kwargs["conversation_config"]["agent"]["prompt"]["tool_ids"]
                    )
                )
            ),
        )

    tool_creations = []

    def create_tool(request):
        tool_creations.append(request.tool_config.name)
        return SimpleNamespace(id="tool-" + request.tool_config.name)

    tools = SimpleNamespace(
        create=create_tool,
        update=lambda tool_id, request: SimpleNamespace(id=tool_id),
    )
    api = SimpleNamespace(
        agents=SimpleNamespace(create=create, get=get, update=update),
        tools=tools,
        secrets=SimpleNamespace(
            create=lambda **k: SimpleNamespace(secret_id="secret-one"), update=lambda *a, **k: None
        ),
    )
    monkeypatch.setattr(setup, "ElevenLabs", lambda **k: SimpleNamespace(conversational_ai=api))
    state = tmp_path / "state.json"
    monkeypatch.setattr(
        "sys.argv", ["setup", "--create-agent", "My airline", "--state-file", str(state)]
    )
    setup.main()
    setup.main()
    assert len(created) == 1
    assert fetched == updated == ["new-agent", "new-agent"]
    assert load_state(state, "new-agent")["agent_id"] == "new-agent"
    # A default creation receipt and a later ID-based update share canonical state.
    monkeypatch.setattr("sys.argv", ["setup", "--create-agent", "Default airline"])
    setup.main()
    count = len(tool_creations)
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "new-agent")
    monkeypatch.setattr("sys.argv", ["setup"])
    setup.main()
    monkeypatch.setattr("sys.argv", ["setup", "--create-agent", "Default airline"])
    setup.main()
    assert len(tool_creations) == count
    assert len(created) == 2
