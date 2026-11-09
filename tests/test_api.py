"""Verify startup and explicit feature boundaries without any external services."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from airline_api.core.config import Settings
from airline_api.main import create_app
from airline_api.modules.voice.tool_contracts import build_tool_contracts
from fastapi.testclient import TestClient
from pydantic import SecretStr


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=SecretStr("postgresql+asyncpg://unused:unused@127.0.0.1:1/unused"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_liveness_works_without_database_or_provider(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}


def test_openapi_is_available_without_integrations(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/voice/webhooks/elevenlabs/book_flight" in response.json()["paths"]


def test_exported_webhook_contracts_match_code_and_openapi(client: TestClient) -> None:
    manifest = json.loads(Path("config/elevenlabs-tools.json").read_text())
    assert manifest == build_tool_contracts()
    paths = client.get("/openapi.json").json()["paths"]
    for tool in manifest["tools"]:
        assert tool["method"].lower() in paths[tool["path"]]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/baggage/inquiries"),
        ("POST", "/requests"),
        ("GET", "/conversations"),
        ("GET", "/conversations/00000000-0000-0000-0000-000000000001"),
        ("GET", "/knowledge/documents"),
        ("POST", "/knowledge/documents"),
        ("POST", "/knowledge/search"),
        ("POST", "/refinement/runs"),
        ("GET", "/refinement/iterations"),
        ("GET", "/refinement/evaluations"),
        ("GET", "/refinement/changes"),
        ("POST", "/voice/sessions"),
    ],
)
def test_removed_platform_routes_are_not_exposed(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, f"/api/v1{path}")
    assert response.status_code == 404
    assert f"/api/v1{path}" not in client.get("/openapi.json").json()["paths"]
