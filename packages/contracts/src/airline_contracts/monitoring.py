"""Read-only observation contracts shared by the worker, API, and dashboard."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

type RunStatus = Literal["running", "passed", "iteration_limit", "error"]
type Stage = Literal[
    "preparing",
    "simulating",
    "evaluating",
    "repairing",
    "verifying",
    "reloading",
    "publishing",
    "rollback",
    "completed",
    "error",
]


class MessageObservation(BaseModel):
    role: Literal["user", "agent"]
    message: str
    occurred_at: datetime


class ToolObservation(BaseModel):
    id: str
    name: str
    status: str
    result: str | None = None


class ScenarioObservation(BaseModel):
    id: str
    goal: str
    status: Literal["pending", "simulating", "evaluating", "passed", "failed", "error"] = "pending"
    conversation_id: str | None = None
    dialogue: list[MessageObservation] = Field(default_factory=list)
    tools: list[ToolObservation] = Field(default_factory=list)
    evaluation: dict[str, JsonValue] | None = None
    errors: list[str] = Field(default_factory=list)


class IterationObservation(BaseModel):
    number: int
    started_at: datetime
    finished_at: datetime | None = None
    stage: Stage = "simulating"
    scenarios: list[ScenarioObservation] = Field(default_factory=list)
    prompt_diff: str = ""
    code_diff: str = ""
    change_status: Literal["none", "proposed", "applied", "rolled_back", "recovery_failed"] = "none"
    repair_explanation: str | None = None
    repair_error: str | None = None


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus = "running"
    stage: Stage = "preparing"
    started_at: datetime
    updated_at: datetime
    heartbeat_at: datetime
    iteration: int = 0
    max_iterations: int
    pass_score: int
    scenario_count: int = 0
    active_scenario: str | None = None
    error: str | None = None


class RunObservation(RunSummary):
    revision: int = 0
    iterations: list[IterationObservation] = Field(default_factory=list)


class MonitoringSnapshot(BaseModel):
    runs: list[RunSummary] = Field(default_factory=list)
    run: RunObservation | None = None
