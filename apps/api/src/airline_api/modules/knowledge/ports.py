"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol
from uuid import UUID

from airline_contracts.types import JsonObject


class KnowledgeSearch(Protocol):
    async def search(self, query: str) -> list[JsonObject]: ...


class KnowledgeIngestion(Protocol):
    async def ingest(self, document: JsonObject) -> None: ...


class KnowledgeRepository(Protocol):
    async def get(self, document_id: UUID) -> JsonObject | None: ...

    async def save(self, document: JsonObject) -> None: ...
