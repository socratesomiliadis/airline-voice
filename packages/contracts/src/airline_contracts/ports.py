"""Integration boundaries shared by application processes."""

from collections.abc import AsyncIterator
from typing import Protocol

from airline_contracts.events import EventEnvelope


class EventPublisher(Protocol):
    async def publish(self, event: EventEnvelope) -> None: ...


class EventSubscriber(Protocol):
    def subscribe(self) -> AsyncIterator[EventEnvelope]: ...
