"""Validated contracts shared by simulation, judging, repair, and run artifacts."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

type Criterion = Literal["understanding", "api_correctness", "outcome_confirmation", "naturalness"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BookingSetup(Contract):
    origin: str = "SFO"
    destination: str = "JFK"
    departure_date: str = "2026-11-09"
    seat_class: str = "economy"
    fare_tier: str = "standard"


class Scenario(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    goal: str = Field(min_length=1)
    customer_facts: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    required_tools: list[str]
    setup: BookingSetup | None = None


class CustomerTurn(Contract):
    message: str
    done: bool


class Simulation(Contract):
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

    def passes(self, threshold: int) -> bool:
        return all(score >= threshold for score in self.scores.model_dump().values())


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
    simulations: list[Simulation] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    repair_applied: bool = False
    repair_error: str | None = None


class RunResult(Contract):
    run_id: str
    status: Literal["passed", "iteration_limit", "error"]
    pass_score: int
    max_iterations: int
    iterations: list[Iteration] = Field(default_factory=list)
    error: str | None = None
