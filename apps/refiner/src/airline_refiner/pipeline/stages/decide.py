"""Evaluate quality thresholds and decide whether to repeat. Interface only; no execution logic."""

from typing import Protocol

from airline_refiner.pipeline.context import IterationContext


class IterationDecider(Protocol):
    async def execute(self, context: IterationContext) -> IterationContext: ...
