"""Shared-secret authentication for trusted agent and simulation clients."""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request

from airline_api.core.config import Settings


async def require_agent_key(
    request: Request,
    key: Annotated[str | None, Header(alias="X-Agent-Api-Key")] = None,
) -> None:
    settings: Settings = request.app.state.settings
    expected = settings.agent_api_key.get_secret_value() if settings.agent_api_key else ""
    if not expected:
        if settings.app_env == "production":
            raise HTTPException(503, detail={"code": "agent_auth_not_configured"})
        return
    if not key or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, detail={"code": "invalid_agent_api_key"})
