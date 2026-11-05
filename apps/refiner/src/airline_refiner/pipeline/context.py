"""Minimal shared stage context; no runtime state machine is defined."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from airline_contracts.types import JsonObject


@dataclass(frozen=True)
class IterationContext:
    iteration_id: UUID
    artifact_directory: Path
    configuration: JsonObject
