"""Identify prompt, integration, or code failures. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class Diagnostician(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
