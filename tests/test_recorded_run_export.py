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
                        "transcript": [
                            {
                                "role": "agent",
                                "message": "private-value",
                                "tool_calls": [
                                    {
                                        "tool_name": "book_flight",
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
    exported = "".join(path.read_text() for path in output.iterdir())
    assert "private-value" not in exported and "private-url" not in exported
    assert "tool_details" not in exported and "headers" not in exported
    run["status"] = "error"
    (source / "run.json").write_text(json.dumps(run))
    with pytest.raises(ValueError, match="completed runs"):
        export_run(source, tmp_path / "incomplete")
