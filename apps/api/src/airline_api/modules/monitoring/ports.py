"""Application boundaries. JsonObject payloads will become domain schemas during implementation."""

from typing import Protocol

from airline_contracts.events import EventEnvelope


class MonitoringEventRepository(Protocol):
    async def append(self, event: EventEnvelope) -> None: ...
