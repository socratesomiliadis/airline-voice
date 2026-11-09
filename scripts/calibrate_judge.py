"""Measure raw judge decisions against labelled cases, before deterministic enforcement.

Run with --output artifacts/judge-calibration.json from the repository root.
Regression expectations are not human labels; report provenance and review status separately.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from airline_refiner.adapters.model import JsonModel
from airline_refiner.adapters.workspace import Artifacts
from airline_refiner.config import Settings, load_config
from airline_refiner.models import Evaluation, Scenario, Simulation
from airline_refiner.pipeline.stages.evaluate import JUDGE, evidence_text
from airline_refiner.policy_checks import check_policy_facts


async def calibrate(
    cases: list[dict[str, Any]], knowledge: dict[str, Any], output: Path
) -> dict[str, Any]:
    settings = Settings()
    if not settings.model_api_key.get_secret_value():
        raise ValueError("Model credentials are required")
    config = load_config(settings.config_path)
    results = []
    async with httpx.AsyncClient(
        base_url=str(settings.model_base_url).rstrip("/") + "/",
        headers={
            "x-api-key": settings.model_api_key.get_secret_value(),
            "anthropic-version": "2026-10-21",
        },
        timeout=config.request_timeout_seconds,
    ) as client:
        model = JsonModel(client, config.model_attempts, config.model_max_tokens)
        for case in cases:
            simulation = Simulation.model_validate(case["simulation"])
            scenario = Scenario.model_validate(case["scenario"])

            def validate(
                evaluation: Evaluation,
                scenario: Scenario = scenario,
                simulation: Simulation = simulation,
            ) -> None:
                if evaluation.scenario_id != scenario.id:
                    raise ValueError("Mismatched calibration scenario")
                if any(f.quote not in evidence_text(simulation) for f in evaluation.failures):
                    raise ValueError("Ungrounded failure quote")

            # Do not use Evaluator.run: its factual guard and retries would hide raw false passes.
            evaluation = await model.generate(
                config.evaluator_model,
                JUDGE,
                {
                    "scenario": scenario.model_dump(mode="json"),
                    "simulation": simulation.model_dump(mode="json"),
                    "knowledge": knowledge,
                    "source": {},
                    "system_prompt": "",
                    "pass_score": config.pass_score,
                    "deterministic_checks": [],
                },
                Evaluation,
                validate,
            )
            observed = {
                c: getattr(evaluation.scores, c) >= config.pass_score for c in case["expected_pass"]
            }
            results.append(
                {
                    "id": case["id"],
                    "label_source": case["label_source"],
                    "human_review_required": case["human_review_required"],
                    "expected_pass": case["expected_pass"],
                    "observed_pass": observed,
                    "agrees": observed == case["expected_pass"],
                    "evaluation": evaluation.model_dump(mode="json"),
                    "factual_checks": [
                        c.model_dump(mode="json") for c in check_policy_facts(simulation)
                    ],
                }
            )
            print(f"Judged {case['id']}: agreement={results[-1]['agrees']}", flush=True)
    report = {
        "model": config.evaluator_model,
        "pass_score": config.pass_score,
        "judge_instruction": JUDGE,
        "cases": results,
        "human_labelled_count": sum(not c["human_review_required"] for c in results),
        "note": "Small calibration set; results apply only to reviewed cases and covered criteria.",
    }
    Artifacts(output.parent, [settings.model_api_key.get_secret_value()]).write(output.name, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("evaluations/judge-calibration.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    knowledge = {p.name: json.loads(p.read_text()) for p in Path("knowledge").glob("*.json")}
    asyncio.run(calibrate(cases, knowledge, args.output))
