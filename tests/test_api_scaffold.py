"""Verify startup and explicit feature boundaries without any external services."""

from collections.abc import Iterator

import pytest
from airline_api.core.config import Settings
from airline_api.main import create_app
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
    assert response.json() == {"status": "ok", "mode": "scaffold"}


def test_openapi_is_available_without_integrations(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/voice/webhooks/elevenlabs" in response.json()["paths"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/bookings"),
        ("POST", "/bookings"),
        ("POST", "/bookings/00000000-0000-0000-0000-000000000001/cancel"),
        ("POST", "/bookings/00000000-0000-0000-0000-000000000001/reschedule"),
        ("POST", "/baggage/inquiries"),
        ("POST", "/requests"),
        ("GET", "/conversations"),
        ("GET", "/conversations/00000000-0000-0000-0000-000000000001"),
        ("GET", "/knowledge/documents"),
        ("POST", "/knowledge/documents"),
        ("POST", "/knowledge/search"),
        ("GET", "/monitoring/events"),
        ("POST", "/refinement/runs"),
        ("GET", "/refinement/iterations"),
        ("GET", "/refinement/evaluations"),
        ("GET", "/refinement/changes"),
        ("POST", "/voice/sessions"),
        ("POST", "/voice/webhooks/elevenlabs"),
    ],
)
def test_feature_routes_are_explicitly_unimplemented(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, f"/api/v1{path}")
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "not_implemented"
