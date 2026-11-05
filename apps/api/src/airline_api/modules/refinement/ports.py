"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol
from uuid import UUID

from airline_contracts.types import JsonObject


class RefinementControl(Protocol):
    async def start(self, configuration: JsonObject) -> UUID: ...


class RefinementRepository(Protocol):
    async def get_iteration(self, iteration_id: UUID) -> JsonObject | None: ...

    async def save_iteration(self, iteration: JsonObject) -> None: ...

    async def save_evaluation(self, evaluation: JsonObject) -> None: ...

    async def save_change(self, change: JsonObject) -> None: ...
