"""Score transcripts and tool outcomes. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class Evaluator(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
