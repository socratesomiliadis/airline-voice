"""Evidence exports preserve actual results and exclude provider credentials."""

import json

import pytest

from scripts.export_refinement_run import export_run


def test_export_preserves_repair_and_scores_without_provider_headers(tmp_path, monkeypatch):
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    monkeypatch.setenv("AGENT_API_KEY", "private-value")
    (source / "initial-prompt.md").write_text("Initial private-value")
    (source / "scenarios.json").write_text('[{"id":"booking"}]')
    iterations = []
    for number, score in [(1, 4), (2, 9)]:
        prefix = source / f"iteration-{number:02d}"
        prefix.mkdir()
        (prefix / "prompt.md").write_text("Initial" if number == 1 else "Final")
        if number == 1:
            (prefix / "repair.json").write_text(
                json.dumps(
                    {
                        "explanation": "Include missing reference",
                        "system_prompt": "Final",
                        "edits": [],
                    }
                )
            )
        iterations.append(
            {
                "number": number,
                "repair_applied": number == 1,
                "repair_error": None,
                "evaluations": [
                    {"scenario_id": "booking", "scores": {"outcome_confirmation": score}}
                ],
                "simulations": [
                    {
                        "scenario_id": "booking",
                        "conversation_id": "fictional-conversation",
                        "completed": True,
                        "errors": [],
                        "cleanup_errors": [],
                        "booking_state": [],
                        "fixture": {
                            "business_time": "2026-11-06T12:00:00Z",
                            "selection_reference": {"source": "trusted_fixture"},
                            "provider_headers": {"key": "private-value"},
                        },
                        "application_failures": [{"stage": "cleanup", "status": 500}],
                        "cleanup_pending": number == 1,
                        "transcript": [
                            {
                                "role": "agent",
                                "message": "private-value",
                                "tool_calls": [
                                    {
                                        "tool_name": "book_flight",
                                        "request_id": "request-1",
                                        "params_as_json": "{}",
                                        "tool_has_been_called": True,
                                        "tool_details": {
                                            "headers": {"X-Agent-Api-Key": "private-value"},
                                            "url": "private-url",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )
    run = {
        "run_id": "real-source-id",
        "status": "passed",
        "pass_score": 8,
        "max_iterations": 5,
        "iterations": iterations,
    }
    (source / "run.json").write_text(json.dumps(run))
    report = export_run(source, output)
    assert report["performance_summary"]["booking"]["change"]["outcome_confirmation"] == 5
    assert report["iterations"][0]["change_explanation"] == "Include missing reference"
    assert (output / "final-prompt.md").read_text() == "Final"
    conversation = report["iterations"][0]["conversations"][0]
    assert conversation["fixture"]["selection_reference"]["source"] == "trusted_fixture"
    assert conversation["fixture"]["business_time"] == "2026-11-06T12:00:00Z"
    assert "provider_headers" not in conversation["fixture"]
    assert conversation["application_failures"] == [{"stage": "cleanup", "status": 500}]
    assert conversation["transcript"][0]["tool_calls"][0]["request_id"] == "request-1"
    exported = "".join(path.read_text() for path in output.iterdir())
    assert "private-value" not in exported and "private-url" not in exported
    assert "tool_details" not in exported and "headers" not in exported
    # New run reports carry their own prompts, scenarios and repair proposals.
    run["initial_prompt"] = "Initial private-value"
    run["final_prompt"] = "Final"
    run["scenario_definitions"] = [{"id": "booking"}]
    for iteration in iterations:
        repair = source / f"iteration-{iteration['number']:02d}/repair.json"
        iteration["repair"] = json.loads(repair.read_text()) if repair.exists() else None
    (source / "run.json").write_text(json.dumps(run))
    import shutil

    for path in list(source.iterdir()):
        if path.name == "run.json":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    standalone = export_run(source / "run.json", tmp_path / "standalone")
    assert standalone["performance_summary"] == report["performance_summary"]
    assert standalone["iterations"][0]["change_explanation"] == "Include missing reference"
    # A cleanup fault can end a diagnostic baseline early. Preserve the explicit
    # missing baseline, rather than refusing the evidence or inventing improvement.
    extra_simulation = {**iterations[-1]["simulations"][0], "scenario_id": "second"}
    iterations[-1]["simulations"].append(extra_simulation)
    iterations[-1]["evaluations"].append(
        {"scenario_id": "second", "scores": {"outcome_confirmation": 9}}
    )
    run["baseline_complete"] = False
    run["final_complete"] = True
    run["performance_summary"] = {
        "second": {"initial": None, "final": {"outcome_confirmation": 9}, "change": None}
    }
    (source / "run.json").write_text(json.dumps(run))
    partial = export_run(source, tmp_path / "partial-baseline")
    assert not partial["baseline_complete"] and partial["final_complete"]
    assert partial["performance_summary"]["second"]["initial"] is None
    assert partial["performance_summary"]["second"]["change"] is None
    run["status"] = "error"
    (source / "run.json").write_text(json.dumps(run))
    with pytest.raises(ValueError, match="completed runs"):
        export_run(source, tmp_path / "incomplete")
    run["error"] = "Provider disconnected"
    iterations[-1]["status"] = "error"
    iterations[-1]["error"] = "Incomplete provider conversation"
    iterations[-1]["evaluations"] = []
    run["final_complete"] = False
    (source / "run.json").write_text(json.dumps(run))
    failed = export_run(source, tmp_path / "failed-evidence", allow_incomplete=True)
    assert failed["status"] == "error" and failed["error"] == "Provider disconnected"
    assert not failed["final_complete"]
    assert not failed["iterations"][-1]["evaluations"]
    assert failed["iterations"][-1]["error"] == "Incomplete provider conversation"
    assert len(failed["iterations"][-1]["conversations"]) == 2
