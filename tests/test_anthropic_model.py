"""Offline checks of the native Anthropic contract and local output validation."""

import asyncio
import json
import sys

import httpx
import pytest
from airline_refiner import cli
from airline_refiner.adapters.model import JsonModel, anthropic_schema
from airline_refiner.config import RefinementConfig, Settings, load_config
from airline_refiner.errors import RefinementError
from airline_refiner.models import CustomerTurn, Evaluation, Repair, RunResult


def message_response(content=None, stop_reason="end_turn"):
    return {
        "stop_reason": stop_reason,
        "content": content
        if content is not None
        else [{"type": "text", "text": '{"message":"Ready","done":true}'}],
    }


@pytest.fixture(autouse=True)
def isolated_model_environment(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "REFINER_MODEL_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_anthropic_settings_and_legacy_key_not_reused(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "old-provider-key")
    assert not Settings(_env_file=None).model_api_key.get_secret_value()
    monkeypatch.setenv("REFINER_MODEL_API_KEY", "worker-key")
    assert Settings(_env_file=None).model_api_key.get_secret_value() == "worker-key"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    settings = Settings(_env_file=None)
    assert settings.model_api_key.get_secret_value() == "anthropic-key"
    assert str(settings.model_base_url) == "https://api.anthropic.com/v1"
    assert "anthropic-key" not in repr(settings)


def test_example_model_config_matches_runtime_defaults():
    from pathlib import Path

    config = load_config(Path("config/refinement.example.toml"))
    defaults = RefinementConfig()
    assert config.customer_model == defaults.customer_model == "claude-haiku-5-5"
    assert config.evaluator_model == defaults.evaluator_model == "claude-sonnet-5-5"
    assert config.repair_model == defaults.repair_model == "claude-sonnet-5-5"
    assert config.model_max_tokens == defaults.model_max_tokens == 16384
    with pytest.raises(ValueError):
        RefinementConfig(model_max_tokens=0)


@pytest.mark.parametrize("schema", [CustomerTurn, Evaluation, Repair])
def test_role_schemas_preserve_requirements_and_move_unsupported_constraints(schema):
    original = schema.model_json_schema()
    transformed = anthropic_schema(original)
    assert schema.model_json_schema() == original
    assert transformed["required"] == original["required"]

    def check(value):
        if isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, dict):
            assert not {"minimum", "maximum", "minLength", "maxLength"} & value.keys()
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
            for item in value.values():
                check(item)

    check(transformed)
    if schema is Evaluation:
        score = transformed["$defs"]["Scores"]["properties"]["understanding"]
        assert '"minimum": 1' in score["description"]
        assert '"maximum": 10' in score["description"]
        rationale = transformed["properties"]["rationale"]
        assert '"minLength": 1' in rationale["description"]


@pytest.mark.parametrize("status", [429, 500, 529])
def test_transient_errors_retry_without_replaying_sensitive_response(status, monkeypatch):
    requests = []

    async def no_sleep(_):
        pass

    monkeypatch.setattr("airline_refiner.adapters.model.asyncio.sleep", no_sleep)

    def transport(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(status, json={"error": "private-provider-detail"})
        return httpx.Response(200, json=message_response())

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1/", transport=httpx.MockTransport(transport)
        ) as client:
            result = await JsonModel(client).generate("test-model", "role", {}, CustomerTurn)
            assert result.message == "Ready"

    asyncio.run(run())
    assert len(requests) == 2
    assert "private-provider-detail" not in json.dumps(requests)


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, {"error": "secret-key"}, "HTTP 401"),
        (400, {"error": "secret-key"}, "HTTP 400"),
        (200, message_response(stop_reason="refusal"), "declined"),
        (200, message_response(stop_reason="max_tokens"), "model_max_tokens"),
    ],
)
def test_terminal_errors_fail_without_retry_or_leaking_provider_body(status, body, error):
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1/", transport=httpx.MockTransport(transport)
        ) as client:
            with pytest.raises(RefinementError, match=error) as exc:
                await JsonModel(client).generate("test-model", "role", {}, CustomerTurn)
            assert "secret-key" not in str(exc.value)

    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize(
    "first_response",
    [
        {"content": []},
        message_response(content=[{"type": "text", "text": "invalid json"}]),
        message_response(content=[{"type": "text", "text": '{"message":"missing done"}'}]),
    ],
)
def test_malformed_output_recovers_with_bounded_retries(first_response, monkeypatch):
    requests = []

    async def no_sleep(_):
        pass

    monkeypatch.setattr("airline_refiner.adapters.model.asyncio.sleep", no_sleep)

    def transport(request):
        requests.append(request)
        body = first_response if len(requests) == 1 else message_response()
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1/", transport=httpx.MockTransport(transport)
        ) as client:
            assert (
                await JsonModel(client, attempts=2).generate("test-model", "role", {}, CustomerTurn)
            ).done

    asyncio.run(run())
    assert len(requests) == 2


def test_cli_uses_native_anthropic_auth_endpoint_and_configured_token_limit(monkeypatch, tmp_path):
    requests = []
    async_client = httpx.AsyncClient

    def transport(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=message_response(
                content=[
                    {"type": "thinking", "thinking": "private reasoning"},
                    {"type": "text", "text": '{"message":"Ready",'},
                    {"type": "text", "text": '"done":true}'},
                ]
            ),
        )

    def client(**kwargs):
        return async_client(**kwargs, transport=httpx.MockTransport(transport))

    class Runner:
        def __init__(self, config, model, *args):
            self.config, self.model = config, model

        async def run(self, run_id):
            result = await self.model.generate(
                self.config.customer_model, "customer", {"goal": "Book"}, CustomerTurn
            )
            assert result.message == "Ready"
            return RunResult(run_id=run_id, status="passed", pass_score=8, max_iterations=5)

    monkeypatch.setattr(cli.httpx, "AsyncClient", client)
    monkeypatch.setattr(cli, "RefinementRunner", Runner)
    settings = Settings(
        _env_file=None,
        ANTHROPIC_API_KEY="test-anthropic-key",
        ELEVENLABS_API_KEY="test-elevenlabs-key",
        ELEVENLABS_AGENT_ID="test-agent",
        artifacts_dir=tmp_path / "artifacts",
    )
    config = RefinementConfig(
        model_max_tokens=8192,
        verification_command=[sys.executable],
        reload_command=[sys.executable],
    )
    assert asyncio.run(cli.execute(settings, config)) == 0
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "test-anthropic-key"
    assert request.headers["anthropic-version"] == "2026-10-21"
    assert "authorization" not in request.headers
    assert "xi-api-key" not in request.headers
    body = json.loads(request.content)
    assert body["max_tokens"] == 8192
    assert body["system"] == "customer"
    assert "response_format" not in body
