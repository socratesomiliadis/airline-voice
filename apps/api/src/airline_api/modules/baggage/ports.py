"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol

from airline_contracts.types import JsonObject


class BaggageService(Protocol):
    async def inquire(self, request: JsonObject) -> JsonObject: ...
