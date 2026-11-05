"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol

from airline_contracts.types import JsonObject


class CustomerRequestService(Protocol):
    async def handle(self, request: JsonObject) -> JsonObject: ...
