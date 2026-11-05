"""Apply candidate changes in an isolated workspace. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class PatchApplier(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
