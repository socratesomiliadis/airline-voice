"""A correct final recommendation cannot excuse a false explanation."""

import asyncio
import json
from pathlib import Path

import pytest
from airline_refiner.config import RefinementConfig
from airline_refiner.models import Evaluation, Scenario, Scores, Simulation
from airline_refiner.pipeline.stages.evaluate import Evaluator
from airline_refiner.policy_checks import check_policy_facts

CLAIM = "Your 24-hour cancellation window has likely passed."


def simulation(now="2026-11-06T12:00:00Z", message=CLAIM):
    return Simulation(
        scenario_id="basic",
        completed=True,
        fixture={"business_time": now, "booking": {"created_at": "2026-11-06T10:00:00Z"}},
        transcript=[{"role": "agent", "message": message}],
    )


@pytest.mark.parametrize(
    "now,passed",
    [
        ("2026-11-06T12:00:00Z", False),
        ("2026-11-07T10:00:00Z", False),
        ("2026-11-07T10:00:01Z", True),
        ("2026-11-05T12:00:00Z", False),
        ("unknown", False),
    ],
)
def test_expired_window_claim_requires_evidence_that_more_than_24_hours_elapsed(now, passed):
    assert check_policy_facts(simulation(now))[0].passed is passed


@pytest.mark.parametrize(
    "message",
    [
        "Your 24-hour cancellation window has not passed.",
        "Your 24-hour cancellation window is still open, but advance purchase fails.",
        "The advance-purchase condition is not met.",
    ],
)
def test_does_not_conflate_elapsed_time_with_advance_purchase_or_negation(message):
    assert not check_policy_facts(simulation(message=message))


def test_optimistic_understanding_score_cannot_override_an_incorrect_elapsed_time_claim():
    class Judge:
        async def generate(self, model, instruction, data, schema, validate):
            result = Evaluation(
                scenario_id="basic",
                scores=Scores(
                    understanding=10, api_correctness=10, outcome_confirmation=10, naturalness=10
                ),
                rationale="Correct restriction",
                failures=[],
            )
            validate(result)
            return result

    scenario = Scenario(
        id="basic",
        goal="Explain",
        customer_facts="Basic ticket",
        expected_outcome="Accurate explanation",
        required_tools=[],
    )
    with pytest.raises(ValueError, match="deterministic"):
        asyncio.run(Evaluator(RefinementConfig(), Judge()).run(scenario, simulation(), "", {}, {}))


def test_actual_recorded_false_explanation_is_caught():
    report = json.loads(Path("examples/recorded-run/report.json").read_text())
    conversation = next(
        c
        for c in report["iterations"][-1]["conversations"]
        if c["scenario_id"] == "basic-change-restriction"
    )
    state = simulation()
    state.transcript = conversation["transcript"]
    checks = check_policy_facts(state)
    assert len(checks) == 1 and not checks[0].passed
    assert "window has likely passed" in checks[0].evidence
