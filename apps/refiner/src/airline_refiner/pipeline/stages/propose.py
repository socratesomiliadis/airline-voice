"""Produce candidate prompt or code changes. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class FixProposer(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
