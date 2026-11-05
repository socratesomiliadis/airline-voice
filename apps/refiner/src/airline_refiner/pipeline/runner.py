"""Future orchestration entry point; deliberately has no loop implementation."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class RefinementRunner(Protocol):
    async def run(self, context: IterationContext) -> None: ...
