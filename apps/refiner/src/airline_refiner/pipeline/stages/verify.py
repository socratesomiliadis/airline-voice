"""Run regression checks and evaluate candidate changes. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class Verifier(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
