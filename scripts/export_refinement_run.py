"""Export a portable, credential-free record of an actual refinement run.

Usage: python scripts/export_refinement_run.py artifacts/RUN_ID --output examples/recorded-run
"""

import argparse
import difflib
import json
import os
from pathlib import Path
from typing import Any

from airline_refiner.adapters.workspace import Artifacts
from dotenv import dotenv_values


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def export_run(source: Path, destination: Path) -> dict[str, Any]:
    run = read_json(source / "run.json")
    config_path, monitor_path = source / "configuration.json", source / "monitor.json"
    config = read_json(config_path) if config_path.exists() else {}
    monitor = read_json(monitor_path) if monitor_path.exists() else {}
    if run["status"] not in {"passed", "iteration_limit"}:
        raise ValueError("Only completed runs can be exported as recorded examples")
    if not run["iterations"] or any(
        not iteration["evaluations"]
        or len(iteration["evaluations"]) != len(iteration["simulations"])
        for iteration in run["iterations"]
    ):
        raise ValueError("Recorded examples require complete simulation and evaluation evidence")
    # Project evidence into an allowlist. Never export provider headers, URLs, debug events,
    # environment settings, source dumps, or arbitrary log files.
    iterations = []
    for iteration in run["iterations"]:
        prefix = source / f"iteration-{iteration['number']:02d}"
        repair_path = prefix / "repair.json"
        repair = read_json(repair_path) if repair_path.exists() else None
        conversations = []
        for simulation in iteration["simulations"]:
            transcript = []
            for turn in simulation["transcript"]:
                transcript.append(
                    {
                        "role": turn.get("role"),
                        "message": turn.get("message"),
                        "tool_calls": [
                            {
                                k: call.get(k)
                                for k in ("tool_name", "params_as_json", "tool_has_been_called")
                            }
                            for call in turn.get("tool_calls") or []
                        ],
                        "tool_results": [
                            {
                                k: result.get(k)
                                for k in ("tool_name", "result_value", "is_error", "is_blocked")
                            }
                            for result in turn.get("tool_results") or []
                        ],
                    }
                )
            conversations.append(
                {
                    "scenario_id": simulation["scenario_id"],
                    "conversation_id": simulation["conversation_id"],
                    "completed": simulation["completed"],
                    "errors": simulation["errors"],
                    "cleanup_errors": simulation["cleanup_errors"],
                    "transcript": transcript,
                    "booking_state": simulation["booking_state"],
                }
            )
        iterations.append(
            {
                "number": iteration["number"],
                "evaluations": iteration["evaluations"],
                "conversations": conversations,
                "repair_applied": iteration["repair_applied"],
                "repair_error": iteration["repair_error"],
                "change_explanation": repair["explanation"] if repair else None,
                "code_edits": repair["edits"] if repair else [],
                "prompt_changed": bool(repair and repair["system_prompt"] is not None),
            }
        )
    first, final = iterations[0], iterations[-1]
    initial_scores = {e["scenario_id"]: e["scores"] for e in first["evaluations"]}
    final_scores = {e["scenario_id"]: e["scores"] for e in final["evaluations"]}
    if initial_scores.keys() != final_scores.keys():
        raise ValueError("First and final iterations must evaluate the same scenarios")
    report = {
        "format": "airline-recorded-run-v1",
        "source_run_id": run["run_id"],
        "started_at": monitor.get("started_at"),
        "finished_at": monitor.get("updated_at"),
        "models": {
            name: config.get(name) for name in ("customer_model", "evaluator_model", "repair_model")
        },
        "status": run["status"],
        "pass_score": run["pass_score"],
        "max_iterations": run["max_iterations"],
        "scenario_definitions": read_json(source / "scenarios.json"),
        "iterations": iterations,
        "performance_summary": {
            name: {
                "initial": initial_scores[name],
                "final": final_scores[name],
                "change": {
                    criterion: score - initial_scores[name][criterion]
                    for criterion, score in final_scores[name].items()
                },
            }
            for name in initial_scores
        },
    }
    initial_prompt = (source / "initial-prompt.md").read_text()
    final_prompt = (source / f"iteration-{final['number']:02d}" / "prompt.md").read_text()
    environment = {**dotenv_values(".env"), **os.environ}
    secrets = [
        value
        for key, value in environment.items()
        if value
        and (
            any(part in key for part in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
            or key == "DATABASE_URL"
        )
    ]
    output = Artifacts(destination, secrets)
    output.write("report.json", report)
    output.write_text("initial-prompt.md", initial_prompt)
    output.write_text("final-prompt.md", final_prompt)
    output.write_text(
        "prompt.patch",
        "".join(
            difflib.unified_diff(
                initial_prompt.splitlines(keepends=True),
                final_prompt.splitlines(keepends=True),
                fromfile="initial-prompt.md",
                tofile="final-prompt.md",
            )
        ),
    )
    return read_json(destination / "report.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = export_run(args.source, args.output)
    print(
        f"Exported {report['status']} run with {len(report['iterations'])} iterations "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
