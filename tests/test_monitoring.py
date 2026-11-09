"""Live observation publishing, durable replay, authentication, and read-only API behavior."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from airline_api.core.config import Settings
from airline_api.main import create_app
from airline_api.modules.monitoring.router import observation_events
from airline_api.modules.monitoring.store import ObservationStore
from airline_refiner.adapters.elevenlabs import ChatSession
from airline_refiner.adapters.workspace import Artifacts
from airline_refiner.config import RefinementConfig
from airline_refiner.models import Evaluation, Repair, Scenario, Scores, Simulation
from airline_refiner.observation import RunObserver
from fastapi.testclient import TestClient
from pydantic import SecretStr


def scenario() -> Scenario:
    return Scenario(
        id="booking",
        goal="Book a ticket",
        customer_facts="One passenger",
        expected_outcome="Confirmed booking",
        required_tools=[],
    )


def observer(root: Path, identifier: str = "run-1") -> RunObserver:
    result = RunObserver(
        identifier, RefinementConfig(), Artifacts(root / identifier, ["private-key"])
    )
    result.start_iteration(1, [scenario()])
    result.phase("simulating", "booking")
    return result


def test_messages_publish_before_conversation_completes_and_secrets_are_redacted(tmp_path):
    async def run():
        writer = observer(tmp_path)
        result = Simulation(scenario_id="booking")
        result._on_change = writer.conversation

        class Socket:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def recv(self):
                return json.dumps(await self.queue.get())

            async def send(self, text):
                pass

            async def close(self):
                pass

        socket = Socket()
        session = ChatSession(socket, result)
        await socket.queue.put(
            {
                "type": "agent_response",
                "agent_response_event": {
                    "agent_response": "Hello private-key",
                },
            }
        )
        await socket.queue.put({"type": "agent_response_complete"})
        await session.receive_turn(1)
        recorded = ObservationStore(tmp_path).snapshot().run
        assert recorded.status == "running" and not result.completed
        assert recorded.iterations[0].scenarios[0].dialogue[0].message == "Hello [REDACTED]"
        await session.send("A ticket, please")
        assert (
            len(ObservationStore(tmp_path).snapshot().run.iterations[0].scenarios[0].dialogue) == 2
        )
        await session.close()

    asyncio.run(run())


def test_evaluations_prompt_diffs_and_rollback_survive_api_restart(tmp_path):
    writer = observer(tmp_path)
    writer.evaluated(
        Evaluation(
            scenario_id="booking",
            scores=Scores(
                understanding=9,
                api_correctness=9,
                outcome_confirmation=9,
                naturalness=9,
            ),
            rationale="All criteria passed",
            failures=[],
        )
    )
    writer.proposed(
        Repair(explanation="Clarify a confirmation", system_prompt="New prompt", edits=[]),
        "Old prompt",
    )
    writer.patch("--- a/service.py\n+++ b/service.py\n")
    writer.phase("rollback")
    writer.repaired("Provider unavailable")
    writer.finish("error", "Unable to restore provider")
    # A new store instance represents an API reload with no process-local state.
    snapshot = ObservationStore(tmp_path).snapshot("run-1")
    assert snapshot.run.status == "error" and snapshot.run.stage == "error"
    iteration = snapshot.run.iterations[0]
    assert iteration.scenarios[0].evaluation["scores"]["understanding"] == 9
    assert "-Old prompt\n+New prompt\n" in iteration.prompt_diff
    assert (
        iteration.change_status == "rolled_back"
        and iteration.repair_error == "Provider unavailable"
    )
    assert iteration.finished_at
    assert "prompt.patch" in {path.name for path in (tmp_path / "run-1/iteration-01").iterdir()}


def test_history_contains_independent_iterations_and_active_scenario(tmp_path):
    writer = observer(tmp_path)
    writer.conversation(
        Simulation(scenario_id="booking", dialogue=[{"role": "user", "message": "First"}])
    )
    writer.start_iteration(2, [scenario()])
    writer.phase("evaluating", "booking")
    writer.conversation(
        Simulation(scenario_id="booking", dialogue=[{"role": "user", "message": "Second"}])
    )
    snapshot = ObservationStore(tmp_path).snapshot().run
    assert snapshot.iteration == 2 and snapshot.active_scenario == "booking"
    assert snapshot.iterations[0].finished_at
    assert [item.scenarios[0].dialogue[0].message for item in snapshot.iterations] == [
        "First",
        "Second",
    ]


def test_store_skips_invalid_files_symlinks_and_selects_latest_run(tmp_path):
    writer = observer(tmp_path, "older")
    writer.state.started_at = datetime.now(UTC) - timedelta(days=1)
    writer.publish()
    observer(tmp_path, "newer")
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken/monitor.json").write_text("invalid JSON")
    (tmp_path / "linked").symlink_to(tmp_path / "newer", target_is_directory=True)
    snapshot = ObservationStore(tmp_path).snapshot()
    assert [item.run_id for item in snapshot.runs] == ["newer", "older"]
    assert snapshot.run.run_id == "newer"
    with pytest.raises(FileNotFoundError):
        ObservationStore(tmp_path).snapshot("missing")


def test_sse_changes_while_running_and_reconnect_replays_current_snapshot(tmp_path):
    async def run():
        writer = observer(tmp_path)
        store = ObservationStore(tmp_path)

        class Request:
            async def is_disconnected(self):
                return False

        stream = observation_events(store, Request(), "run-1")
        assert await anext(stream) == "retry: 2000\n\n"
        first = await anext(stream)
        assert "event: snapshot" in first and '"dialogue":[]' in first
        writer.conversation(
            Simulation(scenario_id="booking", dialogue=[{"role": "user", "message": "Live turn"}])
        )
        second = await anext(stream)
        assert "Live turn" in second and first.splitlines()[0] != second.splitlines()[0]
        await stream.aclose()
        reconnected = observation_events(ObservationStore(tmp_path), Request(), "run-1")
        await anext(reconnected)
        assert "Live turn" in await anext(reconnected)
        await reconnected.aclose()

    asyncio.run(run())


def test_monitoring_is_authenticated_get_only_and_has_no_run_controls(tmp_path):
    observer(tmp_path)
    settings = Settings(
        _env_file=None,
        app_env="test",
        refiner_artifacts_dir=tmp_path,
        agent_api_key=SecretStr("monitor-key"),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/monitoring/snapshot").status_code == 401
        assert client.get("/api/v1/monitoring/events").status_code == 401
        headers = {"X-Agent-Api-Key": "monitor-key"}
        response = client.get("/api/v1/monitoring/snapshot", headers=headers)
        assert response.status_code == 200
        assert response.json()["run"]["run_id"] == "run-1"
        for endpoint in ("snapshot", "events"):
            assert client.post(f"/api/v1/monitoring/{endpoint}", headers=headers).status_code == 405
        assert (
            client.get("/api/v1/monitoring/snapshot?run_id=../other", headers=headers).status_code
            == 422
        )
        assert (
            client.get("/api/v1/monitoring/events?run_id=missing", headers=headers).status_code
            == 404
        )
        assert client.post("/api/v1/refinement/runs", headers=headers).status_code == 404


def test_empty_monitoring_is_an_honest_empty_state_without_database(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        refiner_artifacts_dir=tmp_path,
        database_url=SecretStr("postgresql+asyncpg://unused:unused@127.0.0.1:1/unused"),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/monitoring/snapshot").json() == {"runs": [], "run": None}


def test_tool_status_and_agent_corrections_replace_existing_observations(tmp_path):
    writer = observer(tmp_path)
    result = Simulation(
        scenario_id="booking",
        dialogue=[{"role": "agent", "message": "Earlier"}],
        events=[
            {
                "type": "agent_tool_request",
                "agent_tool_request": {"tool_call_id": "tool-1", "tool_name": "book_flight"},
            },
        ],
    )
    writer.conversation(result)
    timestamp = writer.state.iterations[0].scenarios[0].dialogue[0].occurred_at
    result.dialogue[0]["message"] = "Corrected"
    result.events.append(
        {
            "type": "agent_tool_response_full_payload",
            "agent_tool_response_full_payload": {
                "tool_call_id": "tool-1",
                "tool_name": "book_flight",
                "status": "error",
                "is_error": True,
                "full_tool_result": "Invalid request",
            },
        }
    )
    writer.conversation(result)
    scenario_state = writer.state.iterations[0].scenarios[0]
    assert scenario_state.dialogue[0].occurred_at == timestamp
    assert scenario_state.dialogue[0].message == "Corrected"
    assert len(scenario_state.tools) == 1 and scenario_state.tools[0].status == "error"
