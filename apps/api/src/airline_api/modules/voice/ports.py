"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol

from airline_contracts.types import JsonObject


class VoiceGateway(Protocol):
    async def create_session(self, configuration: JsonObject) -> JsonObject: ...


class VoiceWebhookVerifier(Protocol):
    async def verify(self, body: bytes, signature: str) -> None: ...


class VoiceToolDispatcher(Protocol):
    async def dispatch(self, tool_name: str, arguments: JsonObject) -> JsonObject: ...
