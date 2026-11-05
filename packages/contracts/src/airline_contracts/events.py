"""Proposed monitoring event envelope; publishing and transport are not implemented."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from airline_contracts.types import JsonObject


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name: str
    occurred_at: datetime
    correlation_id: UUID
    payload: JsonObject
