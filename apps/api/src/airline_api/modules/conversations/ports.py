"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol
from uuid import UUID

from airline_contracts.types import JsonObject


class ConversationRepository(Protocol):
    async def get(self, conversation_id: UUID) -> JsonObject | None: ...

    async def save(self, conversation: JsonObject) -> None: ...
