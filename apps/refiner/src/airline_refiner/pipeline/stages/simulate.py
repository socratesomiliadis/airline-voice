"""Generate and run customer conversation scenarios. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class Simulator(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
