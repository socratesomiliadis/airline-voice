"""Validated contracts shared by simulation, judging, repair, and run artifacts."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PrivateAttr, model_validator

type Criterion = Literal["understanding", "api_correctness", "outcome_confirmation", "naturalness"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BookingSetup(Contract):
    origin: str = "SFO"
    destination: str = "JFK"
    departure_date: str = "2026-11-09"
    seat_class: str = "economy"
    fare_tier: str = "standard"


class ItemExpectation(Contract):
    item_type: str
    count: int = Field(ge=1)
    status: Literal["confirmed", "pending_confirmation"]


class OutcomeExpectations(Contract):
    booking_status: Literal["confirmed", "cancelled"] | None = None
    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    seat_class: str | None = None
    fare_tier: str | None = None
    seat_preference: Literal["window", "aisle", "extra_legroom"] | None = None
    items: list[ItemExpectation] = Field(default_factory=list)
    item_charge_cents: int | None = Field(default=None, ge=0)
    full_refund: bool = False
    forbid_mutations: bool = False
    unchanged_booking: bool = False
    tool_order: list[list[str]] = Field(default_factory=list)
    tool_parameters: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    selection: Literal["earliest", "cheapest"] | None = None


class Scenario(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    goal: str = Field(min_length=1)
    customer_facts: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    required_tools: list[str]
    setup: BookingSetup | None = None
    assertions: OutcomeExpectations = Field(default_factory=OutcomeExpectations)


class CustomerTurn(Contract):
    message: str
    done: bool


class Simulation(Contract):
    _on_change: Callable[["Simulation"], None] | None = PrivateAttr(default=None)

    def notify(self) -> None:
        if self._on_change:
            self._on_change(self)

    scenario_id: str
    conversation_id: str | None = None
    dialogue: list[dict[str, Any]] = Field(default_factory=list)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    fixture: dict[str, Any] = Field(default_factory=dict)
    booking_state: list[dict[str, Any]] = Field(default_factory=list)
    completed: bool = False
    errors: list[str] = Field(default_factory=list)
    cleanup_errors: list[str] = Field(default_factory=list)


class Scores(Contract):
    understanding: int = Field(ge=1, le=10, strict=True)
    api_correctness: int = Field(ge=1, le=10, strict=True)
    outcome_confirmation: int = Field(ge=1, le=10, strict=True)
    naturalness: int = Field(ge=1, le=10, strict=True)


class CodeFault(Contract):
    path: str = Field(min_length=1)
    function: str = Field(min_length=1, description="Qualified name, e.g. BookingService.cancel")
    behavior: str = Field(
        min_length=1, description="Observed faulty behavior and expected behavior"
    )


class OutcomeCheck(Contract):
    name: str
    passed: bool
    explanation: str
    evidence: str = ""


class Failure(Contract):
    criterion: Criterion
    root_cause: Literal["prompt", "code"]
    quote: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    code_faults: list[CodeFault]

    @model_validator(mode="after")
    def diagnosis_matches_cause(self) -> Self:
        if (self.root_cause == "code") != bool(self.code_faults):
            raise ValueError(
                "Code failures require code_faults; prompt failures require an empty list"
            )
        return self


class Evaluation(Contract):
    scenario_id: str
    scores: Scores
    rationale: str = Field(min_length=1)
    failures: list[Failure]
    checks: list[OutcomeCheck] = Field(default_factory=list)

    def passes(self, threshold: int) -> bool:
        return all(check.passed for check in self.checks) and all(
            score >= threshold for score in self.scores.model_dump().values()
        )


class FileEdit(Contract):
    path: str
    function: str = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str


class Repair(Contract):
    explanation: str
    system_prompt: str | None
    edits: list[FileEdit]

    @model_validator(mode="after")
    def nonempty_prompt(self) -> Self:
        if self.system_prompt is not None and not self.system_prompt.strip():
            raise ValueError("A rewritten prompt cannot be empty")
        return self


class Iteration(Contract):
    number: int
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    status: Literal["running", "completed", "error"] = "running"
    error: str | None = None
    simulations: list[Simulation] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    repair_applied: bool = False
    repair_error: str | None = None
    repair: Repair | None = None
    change_status: Literal["none", "proposed", "applied", "rolled_back", "recovery_failed"] = "none"
    prompt_before: str | None = None
    prompt_after: str | None = None
    prompt_diff: str = ""
    code_diff: str = ""
    source_sha256: str | None = None
    verification: dict[str, Any] | None = None
    execution_logs: dict[str, str] = Field(default_factory=dict)


class ScenarioPerformance(Contract):
    initial: Scores | None = None
    final: Scores | None = None
    change: dict[str, int] | None = None


class RunResult(Contract):
    format_version: Literal["airline-refinement-run-v2"] = "airline-refinement-run-v2"
    run_id: str
    status: Literal["running", "passed", "iteration_limit", "error"]
    pass_score: int
    max_iterations: int
    iterations: list[Iteration] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    scenario_definitions: list[Scenario] = Field(default_factory=list)
    initial_prompt: str | None = None
    final_prompt: str | None = None
    initial_source_sha256: str | None = None
    final_source_sha256: str | None = None
    performance_summary: dict[str, ScenarioPerformance] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    baseline_complete: bool = False
    final_complete: bool = False
    deployment_consistent: bool = True
