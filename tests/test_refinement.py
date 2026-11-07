"""Offline behavioral tests of autonomous iteration, provider contracts and recovery."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from airline_refiner.adapters.api import AirlineAPI
from airline_refiner.adapters.elevenlabs import CLIENT_EVENTS, ChatSession, ElevenLabs
from airline_refiner.adapters.model import JsonModel
from airline_refiner.adapters.workspace import Artifacts, Workspace
from airline_refiner.cli import main
from airline_refiner.config import (
    MAX_ITERATIONS,
    PASS_SCORE,
    RefinementConfig,
    Settings,
    load_config,
)
from airline_refiner.errors import RefinementError
from airline_refiner.models import (
    CodeFault,
    CustomerTurn,
    Evaluation,
    Failure,
    FileEdit,
    Iteration,
    Repair,
    Scenario,
    Scores,
    Simulation,
)
from airline_refiner.pipeline.runner import RefinementRunner, load_scenarios
from airline_refiner.pipeline.stages.evaluate import Evaluator
from airline_refiner.pipeline.stages.propose import FixProposer
from airline_refiner.pipeline.stages.simulate import Simulator


def service_source(value=1):
    return f"def quote():\n    return {value}\n\n\ndef untouched():\n    return 99\n"


def code_fault(path="backend/service.py", function="quote"):
    return CodeFault(
        path=path, function=function, behavior="Returns the wrong fare; return the requested fare"
    )


class ScriptedModel:
    """Exercises real stages and their validators with deterministic model responses."""

    def __init__(self, fail_rounds: int = 1, cause: str = "mixed") -> None:
        self.fail_rounds, self.cause = fail_rounds, cause
        self.calls: list[tuple[str, str]] = []
        self.judged = 0
        self.repairs = 0
        self.repair_inputs = []

    async def generate(self, model, instruction, data, schema, validate=None):
        self.calls.append((model, schema.__name__))
        if schema is CustomerTurn:
            result = CustomerTurn(message="Please book it. Thank you, that is all.", done=True)
        elif schema is Evaluation:
            self.judged += 1
            bad = self.judged <= self.fail_rounds
            failures = []
            if bad and self.cause in {"prompt", "mixed"}:
                failures.append(
                    Failure(
                        criterion="understanding",
                        root_cause="prompt",
                        quote="Wrong response",
                        explanation="Agent misunderstood the destination",
                        code_faults=[],
                    )
                )
            if bad and self.cause in {"code", "mixed"}:
                failures.append(
                    Failure(
                        criterion="api_correctness",
                        root_cause="code",
                        quote="Wrong response",
                        explanation="A correct request returned incorrect data",
                        code_faults=[
                            CodeFault(
                                path="backend/service.py",
                                function="quote",
                                behavior="Returns the wrong fare; return the requested fare",
                            )
                        ],
                    )
                )
            scores = Scores(
                understanding=9, api_correctness=9, outcome_confirmation=9, naturalness=9
            )
            for failure in failures:
                setattr(scores, failure.criterion, 4)
            result = Evaluation(
                scenario_id=data["scenario"]["id"],
                scores=scores,
                rationale="Grounded in transcript and persisted state",
                failures=failures,
            )
        elif schema is Repair:
            self.repair_inputs.append(data)
            self.repairs += 1
            result = Repair(
                explanation="Correct destination understanding and the backend result",
                system_prompt=f"Improved prompt {self.repairs}" if self.cause != "code" else None,
                edits=[
                    FileEdit(
                        path="backend/service.py",
                        function="quote",
                        old_text=f"return {self.repairs}",
                        new_text=f"return {self.repairs + 1}",
                    )
                ]
                if self.cause != "prompt"
                else [],
            )
        else:
            raise AssertionError(schema)
        if validate:
            validate(result)
        return result


class FakeSession:
    def __init__(self, result):
        self.result = result
        self.closed = False
        self.turns = 0

    async def receive_turn(self, timeout_seconds):
        self.turns += 1
        self.result.conversation_id = "conv-test"
        self.result.dialogue.append({"role": "agent", "message": "Wrong response"})

    async def send(self, message):
        self.result.dialogue.append({"role": "user", "message": message})

    async def close(self):
        self.closed = True


class FakeProvider:
    def __init__(self):
        self.updates = []
        self.sessions = []

    async def configure_chat(self):
        return "Original prompt"

    async def update_prompt(self, prompt):
        self.updates.append(prompt)

    async def connect(self, result):
        session = FakeSession(result)
        self.sessions.append(session)
        return session

    async def transcript(self, conversation_id, timeout_seconds):
        return [
            {
                "role": "agent",
                "message": "Wrong response",
                "tool_calls": [
                    {
                        "tool_name": "book_flight",
                        "tool_has_been_called": True,
                        "params_as_json": '{"flight_id":"flight-1"}',
                    },
                ],
            }
        ]


class FakeAPI:
    def __init__(self):
        self.cleanups = []
        self.ready_calls = 0

    async def ready(self, timeout_seconds):
        self.ready_calls += 1

    async def prepare(self, scenario, caller):
        return {"passenger": {"passenger_id": caller, "full_name": "Jordan Taylor"}}

    async def capture(self, fixture, conversation_id):
        return [{"reference": "ABC123", "status": "confirmed"}]

    async def cleanup(self, fixture, conversation_id, caller):
        self.cleanups.append(caller)


@pytest.fixture
def rig(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/service.py").write_text(service_source(1))
    (tmp_path / "backend/unrelated.py").write_text("UNCHANGED = True\n")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge/policy.json").write_text('{"policy": "fictional"}')
    (tmp_path / "prompt.md").write_text("Original local prompt\n")
    (tmp_path / "scenarios.json").write_text(
        json.dumps(
            [
                {
                    "id": "booking",
                    "goal": "Book travel",
                    "customer_facts": "One passenger",
                    "expected_outcome": "Confirmed booking",
                    "required_tools": ["book_flight"],
                }
            ]
        )
    )
    config = RefinementConfig(
        workspace_root=tmp_path,
        scenarios_path=Path("scenarios.json"),
        prompt_path=Path("prompt.md"),
        editable_roots=["backend"],
        verification_command=[sys.executable, "-c", "assert True"],
        reload_command=[sys.executable, "-c", "open('reloaded', 'a').write('reload\\n')"],
    )
    model, provider, api = ScriptedModel(), FakeProvider(), FakeAPI()
    workspace = Workspace(config)
    artifacts = Artifacts(tmp_path / "artifacts")
    runner = RefinementRunner(config, model, provider, api, workspace, artifacts)
    return runner, config, model, provider, api, tmp_path


def test_mixed_repairs_are_applied_reloaded_published_and_retested(rig):
    runner, _, model, provider, api, root = rig
    result = asyncio.run(runner.run("run-1"))
    assert result.status == "passed"
    assert len(result.iterations) == 2
    assert result.iterations[0].repair_applied
    assert model.repairs == 1
    repair_input = model.repair_inputs[0]
    assert set(repair_input["source"]) == {"backend/service.py"}
    assert repair_input["code_faults"] == [code_fault().model_dump()]
    assert (root / "backend/unrelated.py").read_text() == "UNCHANGED = True\n"
    assert (root / "backend/service.py").read_text() == service_source(2)
    assert (root / "reloaded").read_text() == "reload\n"
    assert provider.updates == ["Improved prompt 1"]
    assert (root / "prompt.md").read_text() == "Improved prompt 1\n"
    assert len(api.cleanups) == 2 and len(set(api.cleanups)) == 2
    assert all(session.closed for session in provider.sessions)
    assert "return 2" in (root / "artifacts/iteration-01/code.patch").read_text()
    report = json.loads((root / "artifacts/run.json").read_text())
    assert report["status"] == "passed"
    observed = json.loads((root / "artifacts/monitor.json").read_text())
    assert observed["status"] == "passed" and observed["stage"] == "completed"
    assert len(observed["iterations"]) == 2
    assert observed["iterations"][0]["change_status"] == "applied"
    assert "+Improved prompt 1" in observed["iterations"][0]["prompt_diff"]
    assert observed["iterations"][0]["scenarios"][0]["evaluation"]["scores"]["understanding"] == 4
    assert observed["iterations"][1]["scenarios"][0]["dialogue"]
    assert report["iterations"][0]["evaluations"][0]["failures"][1]["root_cause"] == "code"
    assert model.calls == [
        ("gpt-4.1-mini", "CustomerTurn"),
        ("gpt-4.1", "Evaluation"),
        ("gpt-4.1", "Repair"),
        ("gpt-4.1-mini", "CustomerTurn"),
        ("gpt-4.1", "Evaluation"),
    ]


@pytest.mark.parametrize("cause", ["prompt", "code"])
def test_single_cause_only_changes_its_target(rig, cause):
    runner, _, model, provider, _, root = rig
    model.cause = cause
    assert asyncio.run(runner.run()).status == "passed"
    assert bool(provider.updates) == (cause == "prompt")
    assert (root / "reloaded").exists() == (cause == "code")
    assert ((root / "backend/service.py").read_text() != service_source(1)) == (cause == "code")


def test_iteration_limit_includes_baseline_and_never_deploys_untested_final_fix(rig):
    runner, config, model, _, _, root = rig
    config.max_iterations = 3
    model.fail_rounds = 100
    result = asyncio.run(runner.run())
    assert result.status == "iteration_limit"
    assert len(result.iterations) == 3 and model.repairs == 2
    assert not result.iterations[-1].repair_applied
    assert (root / "backend/service.py").read_text() == service_source(3)


def test_all_scenarios_rerun_and_one_low_criterion_prevents_pass(rig):
    runner, _, model, _, api, root = rig
    data = json.loads((root / "scenarios.json").read_text())
    data.append({**data[0], "id": "another-booking"})
    (root / "scenarios.json").write_text(json.dumps(data))
    model.fail_rounds = 1
    result = asyncio.run(runner.run())
    assert result.status == "passed"
    assert [len(i.evaluations) for i in result.iterations] == [2, 2]
    assert len(api.cleanups) == 4


def test_initially_passing_suite_makes_no_changes(rig):
    runner, _, model, provider, _, root = rig
    model.fail_rounds = 0
    result = asyncio.run(runner.run())
    assert result.status == "passed" and len(result.iterations) == 1
    assert model.repairs == 0 and not provider.updates and not (root / "reloaded").exists()


def test_verification_failure_restores_code_and_next_iteration_recovers(rig):
    runner, config, _, provider, _, root = rig
    config.verification_command = [sys.executable, "-c", "raise SystemExit(1)"]
    result = asyncio.run(runner.run())
    assert result.status == "passed"
    assert "exited 1" in result.iterations[0].repair_error
    assert not result.iterations[0].repair_applied
    assert (root / "backend/service.py").read_text() == service_source(1)
    assert provider.updates == []
    assert (root / "reloaded").read_text() == "reload\n"  # Restored service reload.


def test_failed_reload_rolls_back_and_restores_old_service(rig):
    runner, config, _, _, _, root = rig
    # Fail the first reload, succeed while recovering the original code.
    config.reload_command = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; p=Path('attempt'); "
            "exists=p.exists(); p.touch(); raise SystemExit(0 if exists else 1)"
        ),
    ]
    result = asyncio.run(runner.run())
    assert result.status == "passed"
    assert result.iterations[0].repair_error
    assert (root / "backend/service.py").read_text() == service_source(1)


def test_unrecoverable_reload_stops_instead_of_testing_unknown_state(rig):
    runner, config, model, _, _, root = rig
    config.reload_command = [sys.executable, "-c", "raise SystemExit(1)"]
    result = asyncio.run(runner.run())
    assert result.status == "error" and len(result.iterations) == 1
    assert "rollback" in result.error
    assert model.judged == 1
    assert (root / "backend/service.py").read_text() == service_source(1)


def test_prompt_publish_failure_rolls_back_both_prompt_and_code(rig):
    runner, _, _, provider, _, root = rig
    attempts = []

    async def publish(prompt):
        attempts.append(prompt)
        if prompt != "Original prompt":
            raise RefinementError("Prompt publish failed")

    provider.update_prompt = publish
    result = asyncio.run(runner.run())
    assert result.status == "passed"
    assert attempts == ["Improved prompt 1", "Original prompt"]
    assert (root / "prompt.md").read_text() == "Original local prompt\n"
    assert (root / "backend/service.py").read_text() == service_source(1)
    assert (root / "reloaded").read_text().count("reload") == 2


def test_patch_rejects_traversal_symlinks_ambiguity_syntax_and_stale_source(rig):
    runner, _, _, _, _, root = rig
    workspace = runner.workspace
    sources = workspace.source()
    faults = [code_fault()]
    for path in ("../escape.py", "backend/../../escape.py", "tests/test.py", "/tmp/escape.py"):
        with pytest.raises(RefinementError):
            workspace.plan(
                [FileEdit(path=path, function="quote", old_text="return 1", new_text="return 2")],
                sources,
                faults,
            )
    (root / "backend/link.py").symlink_to(root / "backend/service.py")
    with pytest.raises(RefinementError, match="symlinks"):
        workspace.plan(
            [
                FileEdit(
                    path="backend/link.py",
                    function="quote",
                    old_text="return 1",
                    new_text="return 2",
                )
            ],
            sources,
            faults,
        )
    (root / "backend/link.py").unlink()
    for old, new in (("missing", "return 2"), ("return 1", "not python!")):
        with pytest.raises(RefinementError):
            workspace.plan(
                [FileEdit(path="backend/service.py", function="quote", old_text=old, new_text=new)],
                sources,
                faults,
            )
    (root / "backend/service.py").write_text(service_source(99))
    with pytest.raises(RefinementError, match="stale"):
        workspace.plan(
            [
                FileEdit(
                    path="backend/service.py",
                    function="quote",
                    old_text="return 1",
                    new_text="return 2",
                )
            ],
            sources,
            faults,
        )
    assert (root / "backend/service.py").read_text() == service_source(99)


def test_patch_rejects_new_files_and_enforces_file_limit(rig):
    runner, config, _, _, _, root = rig
    workspace = runner.workspace
    edit = FileEdit(
        path="backend/helper.py", function="quote", old_text="return 1", new_text="return 2"
    )
    with pytest.raises(RefinementError, match="existing"):
        workspace.plan([edit], workspace.source(), [code_fault("backend/helper.py")])
    assert not (root / "backend/helper.py").exists()
    config.max_patch_files = 1
    with pytest.raises(RefinementError, match="max_patch_files"):
        workspace.plan(
            [
                edit,
                FileEdit(
                    path="backend/other.py",
                    function="quote",
                    old_text="return 1",
                    new_text="return 2",
                ),
            ],
            workspace.source(),
            [code_fault("backend/helper.py"), code_fault("backend/other.py")],
        )


def test_patch_rejects_undiagnosed_functions_and_module_level_injection(rig):
    runner, _, _, _, _, root = rig
    sources = runner.workspace.source()
    for function, old, new in (
        ("untouched", "return 99", "return 2"),
        ("quote", "return 99", "return 2"),
        ("quote", "return 1", "return 2\n\nINJECTED = True"),
    ):
        with pytest.raises(RefinementError):
            runner.workspace.plan(
                [
                    FileEdit(
                        path="backend/service.py", function=function, old_text=old, new_text=new
                    )
                ],
                sources,
                [code_fault()],
            )
    assert (root / "backend/service.py").read_text() == service_source(1)


def test_targeted_method_patch_preserves_decorators_other_methods_and_can_rollback(rig):
    runner, _, _, _, _, root = rig
    path = root / "backend/service.py"
    original = (
        "class Fares:\n"
        "    @staticmethod\n"
        "    async def quote():\n"
        "        return 1\n\n"
        "    def untouched(self):\n"
        "        return 1\n"
    )
    path.write_text(original)
    transaction = runner.workspace.plan(
        [
            FileEdit(
                path="backend/service.py",
                function="Fares.quote",
                old_text="return 1",
                new_text="return 2",
            )
        ],
        runner.workspace.source(),
        [code_fault(function="Fares.quote")],
    )
    transaction.apply()
    assert path.read_text() == original.replace("return 1", "return 2", 1)
    transaction.rollback()
    assert path.read_text() == original


def test_workspace_lock_rejects_concurrent_runs(rig):
    runner, _, _, _, _, _ = rig
    with runner.workspace.lock():
        with pytest.raises(RefinementError, match="already"):
            with runner.workspace.lock():
                pass


@pytest.mark.parametrize("mode", ["invented_quote", "missing_cause", "missing_tool", "errors"])
def test_judge_rejects_unsupported_or_false_passing_evaluations(mode):
    scenario = Scenario(
        id="case",
        goal="Book",
        customer_facts="One passenger",
        expected_outcome="Booking",
        required_tools=[],
    )
    simulation = Simulation(
        scenario_id="case",
        completed=True,
        transcript=[{"role": "agent", "message": "Observed response"}],
    )
    evaluation = Evaluation(
        scenario_id="case",
        scores=Scores(
            understanding=9,
            api_correctness=9,
            outcome_confirmation=9,
            naturalness=9,
        ),
        rationale="All fine",
        failures=[],
    )
    if mode == "invented_quote":
        evaluation.scores.understanding = 2
        evaluation.failures = [
            Failure(
                criterion="understanding",
                root_cause="prompt",
                quote="Never happened",
                explanation="Wrong",
                code_faults=[],
            )
        ]
    elif mode == "missing_cause":
        evaluation.scores.naturalness = 2
    elif mode == "missing_tool":
        scenario.required_tools = ["book_flight"]
    else:
        simulation.errors = ["Transcript unavailable"]

    class Model:
        async def generate(self, model, instruction, data, schema, validate):
            validate(evaluation)
            return evaluation

    with pytest.raises(ValueError):
        asyncio.run(
            Evaluator(RefinementConfig(), Model()).run(
                scenario,
                simulation,
                "Prompt",
                {},
                {"policy": "fictional"},
            )
        )


def test_customer_failure_still_closes_session_collects_evidence_and_cleans_up():
    provider, api = FakeProvider(), FakeAPI()

    class BrokenModel:
        async def generate(self, *args, **kwargs):
            raise RefinementError("Model unavailable")

    scenario = Scenario(
        id="case",
        goal="Book",
        customer_facts="One passenger",
        expected_outcome="Booking",
        required_tools=[],
    )
    result = asyncio.run(
        Simulator(RefinementConfig(), BrokenModel(), provider, api).run(scenario, "caller")
    )
    assert result.errors == ["Model unavailable"]
    assert not result.completed and result.transcript and result.booking_state
    assert provider.sessions[0].closed and api.cleanups == ["caller"]


def test_provider_uses_correct_override_nesting_and_preserves_voice_security():
    requests = []

    def transport(request):
        requests.append(request)
        if request.method == "GET" and request.url.path.endswith("get-signed-url"):
            return httpx.Response(200, json={"signed_url": "wss://example.test/private"})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "branch_id": "branch-1",
                    "conversation_config": {
                        "agent": {"prompt": {"prompt": "Existing"}},
                        "conversation": {"client_events": ["audio"]},
                    },
                    "platform_settings": {
                        "auth": {"enable_auth": True},
                        "overrides": {
                            "custom_llm_extra_body": False,
                            "conversation_config_override": {
                                "agent": {"prompt": {"prompt": False}}
                            },
                        },
                    },
                },
            )
        return httpx.Response(200, json={})

    async def run():
        async with httpx.AsyncClient(
            base_url="https://provider.test/v1/", transport=httpx.MockTransport(transport)
        ) as client:
            provider = ElevenLabs(client, "agent-1")
            assert await provider.configure_chat() == "Existing"
            await provider.update_prompt("Updated")
            assert await provider.signed_url() == "wss://example.test/private"

    asyncio.run(run())
    config = json.loads(requests[1].content)
    override = config["platform_settings"]["overrides"]
    assert override["conversation_config_override"]["conversation"]["text_only"] is True
    assert override["conversation_config_override"]["agent"]["prompt"]["prompt"] is False
    assert "auth" not in config["platform_settings"]
    assert set(config["conversation_config"]["conversation"]["client_events"]) == CLIENT_EVENTS | {
        "audio"
    }
    assert json.loads(requests[2].content) == {
        "conversation_config": {"agent": {"prompt": {"prompt": "Updated"}}},
    }
    assert all(request.url.params["branch_id"] == "branch-1" for request in requests[1:])


def test_chat_waits_for_complete_and_answers_pings_between_customer_turns():
    async def run():
        class Socket:
            def __init__(self):
                self.messages = asyncio.Queue()
                self.sent = []

            async def recv(self):
                return json.dumps(await self.messages.get())

            async def send(self, text):
                self.sent.append(json.loads(text))

            async def close(self):
                pass

        socket = Socket()
        result = Simulation(scenario_id="case")
        session = ChatSession(socket, result)
        await socket.messages.put(
            {
                "type": "conversation_initiation_metadata",
                "conversation_initiation_metadata_event": {"conversation_id": "conv"},
            }
        )
        await socket.messages.put(
            {"type": "agent_response", "agent_response_event": {"agent_response": "Checking"}}
        )
        task = asyncio.create_task(session.receive_turn(1))
        await asyncio.sleep(0)
        assert not task.done()  # A tool preamble cannot trigger the next customer message.
        await socket.messages.put(
            {"type": "agent_tool_response", "agent_tool_response": {"tool_name": "search_flights"}}
        )
        await socket.messages.put(
            {"type": "agent_response", "agent_response_event": {"agent_response": "Found flights"}}
        )
        await socket.messages.put(
            {"type": "agent_response_complete", "agent_response_complete_event": {"event_id": 1}}
        )
        await task
        await socket.messages.put({"type": "ping", "ping_event": {"event_id": 42}})
        await asyncio.sleep(0)
        assert socket.sent == [{"type": "pong", "event_id": 42}]
        assert result.conversation_id == "conv" and len(result.dialogue) == 2
        await session.close()
        assert session.reader.done()

    asyncio.run(run())


def test_model_structured_call_retries_invalid_evidence_without_sharing_role_history():
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        message = "bad" if len(requests) == 1 else "good"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"message": message, "done": True}),
                        }
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="https://model.test/v1/", transport=httpx.MockTransport(transport)
        ) as client:
            model = JsonModel(client, attempts=2)

            def validate(turn):
                if turn.message == "bad":
                    raise ValueError("The response must be good")

            result = await model.generate(
                "chosen-model", "Customer role", {"goal": "Book"}, CustomerTurn, validate
            )
            assert result.message == "good"

    asyncio.run(run())
    assert len(requests) == 2
    assert requests[0]["model"] == "chosen-model"
    assert requests[0]["response_format"]["json_schema"]["strict"] is True
    assert requests[0]["messages"][0]["content"] == "Customer role"
    assert "response must be good" in requests[1]["messages"][-1]["content"]


def test_missing_model_credential_fails_before_network_or_mutation(monkeypatch, capsys):
    monkeypatch.setattr(
        "airline_refiner.cli.Settings",
        lambda: Settings(
            _env_file=None,
            ELEVENLABS_API_KEY="example",
            ELEVENLABS_AGENT_ID="agent",
            REFINER_MODEL_API_KEY="",
        ),
    )
    monkeypatch.setattr("sys.argv", ["airline-refiner", "run"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "REFINER_MODEL_API_KEY" in capsys.readouterr().err


def test_defaults_suite_validation_and_artifact_secret_redaction(tmp_path):
    config = load_config(Path("config/refinement.example.toml"))
    assert config.pass_score == PASS_SCORE == 8
    assert config.max_iterations == MAX_ITERATIONS == 5
    assert len(load_scenarios(Path("scenarios/airline.json"))) == 8
    path = tmp_path / "invalid.json"
    for data in ([], [{"id": "bad"}]):
        path.write_text(json.dumps(data))
        with pytest.raises((ValueError, RefinementError)):
            load_scenarios(path)
    artifacts = Artifacts(tmp_path / "artifacts", ["secret-token"])
    artifacts.write("report.json", {"error": "leaked secret-token"})
    assert "secret-token" not in (artifacts.directory / "report.json").read_text()
    assert "[REDACTED]" in (artifacts.directory / "report.json").read_text()


def test_airline_readiness_requires_database_and_inventory_not_just_health():
    async def run():
        def transport(request):
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(503, json={"error": "DB unavailable"})

        async with httpx.AsyncClient(
            base_url="https://api.test/", transport=httpx.MockTransport(transport)
        ) as client:
            with pytest.raises(RefinementError, match="ready"):
                await AirlineAPI(client).ready(0.01)

    asyncio.run(run())


def test_local_reload_waits_for_free_port_and_preserves_existing_command(monkeypatch, tmp_path):
    from airline_refiner import reload_service

    state = tmp_path / "service/command.json"
    observations = iter([{321}, set(), set(), set(), {654}])
    monkeypatch.setattr(reload_service, "listeners", lambda port: next(observations))
    monkeypatch.setattr(
        reload_service,
        "output",
        lambda command: (
            ".venv/bin/python -m uvicorn airline_api.main:app --host 127.0.0.1 --port 8000"
        ),
    )
    monkeypatch.setattr(reload_service.time, "sleep", lambda seconds: None)
    killed, launched = [], []
    monkeypatch.setattr(reload_service.os, "kill", lambda pid, sig: killed.append(pid))

    class Process:
        pid = 654

        def poll(self):
            return None

    def start(command, **kwargs):
        launched.append(command)
        return Process()

    monkeypatch.setattr(reload_service.subprocess, "Popen", start)
    reload_service.reload_local(8000, {321}, state)
    assert killed == [321] and len(launched) == 1
    assert launched[0] == json.loads(state.read_text())
    assert launched[0][2:4] == ["uvicorn", "airline_api.main:app"]


def test_local_reload_refuses_unrelated_listener(monkeypatch, tmp_path):
    from airline_refiner import reload_service

    monkeypatch.setattr(reload_service, "output", lambda command: "python unrelated_server.py")
    monkeypatch.setattr(
        reload_service.os, "kill", lambda *args: pytest.fail("Must not kill another app")
    )
    with pytest.raises(RefinementError, match="unrecognized"):
        reload_service.reload_local(8000, {321}, tmp_path / "command.json")


def test_local_reload_recovery_uses_saved_command_when_candidate_did_not_start(
    monkeypatch, tmp_path
):
    from airline_refiner import reload_service

    state = tmp_path / "command.json"
    command = [sys.executable, "-m", "uvicorn", "airline_api.main:app", "--port", "8000"]
    state.write_text(json.dumps(command))
    observations = iter([set(), {654}])
    monkeypatch.setattr(reload_service, "listeners", lambda port: next(observations))
    process = type("Process", (), {"pid": 654})()
    launched = []

    def start(argv, **kwargs):
        launched.append(argv)
        return process

    monkeypatch.setattr(reload_service.subprocess, "Popen", start)
    reload_service.reload_local(8000, set(), state)
    assert launched == [command]


def test_cli_overrides_both_limits(monkeypatch, capsys):
    observed = []

    async def execute(settings, config):
        observed.append(config)
        return 0

    monkeypatch.setattr("airline_refiner.cli.execute", execute)
    monkeypatch.setattr(
        "sys.argv", ["airline-refiner", "run", "--pass-score", "9", "--max-iterations", "2"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert observed[0].pass_score == 9 and observed[0].max_iterations == 2


def test_exact_threshold_passes_but_one_lower_score_does_not():
    evaluation = Evaluation(
        scenario_id="case",
        scores=Scores(
            understanding=8,
            api_correctness=8,
            outcome_confirmation=8,
            naturalness=8,
        ),
        rationale="All criteria meet the threshold",
        failures=[],
    )
    assert evaluation.passes(8)
    evaluation.scores.outcome_confirmation = 7
    assert not evaluation.passes(8)


def test_real_fixture_lifecycle_releases_inventory_between_iterations(postgres_url):
    from airline_api.infrastructure.database.seed import load_dataset, seed_dataset
    from airline_api.main import create_app

    from tests.test_bookings_api import HEADERS, settings

    async def run():
        await seed_dataset(postgres_url, load_dataset())
        app = create_app(settings(postgres_url))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                base_url="http://test/",
                headers=HEADERS,
                transport=httpx.ASGITransport(app=app),
            ) as client:
                api = AirlineAPI(client)
                await api.ready(1)
                query = {
                    "origin": "SFO",
                    "destination": "JFK",
                    "departure_date": "2026-11-09",
                    "seat_class": "economy",
                    "fare_tier": "standard",
                    "limit": 1,
                }
                initial = (await client.get("api/v1/flights", params=query)).json()["offers"][0][
                    "available_seats"
                ]
                for number in (1, 2):
                    for scenario in load_scenarios(Path("scenarios/airline.json")):
                        caller = f"fixture-{number}-{scenario.id}"
                        fixture = await api.prepare(scenario, caller)
                        state = await api.capture(fixture, None)
                        if scenario.setup:
                            assert state[0]["status"] == "confirmed"
                            assert state[0]["passengers"][0]["passenger_id"] == caller
                        else:
                            assert state == []
                        await api.cleanup(fixture, None, caller)
                        if scenario.setup:
                            after = await api.capture(fixture, None)
                            assert after[0]["status"] == "cancelled"
                final = (await client.get("api/v1/flights", params=query)).json()["offers"][0][
                    "available_seats"
                ]
                assert final == initial

    asyncio.run(run())


def test_malformed_backend_evidence_and_cleanup_are_recorded_without_losing_transcript():
    provider, api = FakeProvider(), FakeAPI()

    async def malformed(*args):
        raise KeyError("unexpected backend response shape")

    api.capture = malformed
    api.cleanup = malformed
    scenario = Scenario(
        id="case",
        goal="Book",
        customer_facts="One passenger",
        expected_outcome="Booking",
        required_tools=[],
    )
    result = asyncio.run(
        Simulator(RefinementConfig(), ScriptedModel(), provider, api).run(scenario, "caller")
    )
    assert result.transcript
    assert result.errors == ["Booking evidence collection failed (KeyError)"]
    assert result.cleanup_errors == ["Fixture cleanup failed (KeyError)"]
    assert provider.sessions[0].closed


@pytest.mark.parametrize(
    "path,function",
    [
        ("backend/missing.py", "quote"),
        ("backend/service.py", "missing"),
    ],
)
def test_evaluator_rejects_code_diagnosis_without_existing_file_and_function(path, function):
    scenario = Scenario(
        id="case",
        goal="Book",
        customer_facts="One passenger",
        expected_outcome="Booking",
        required_tools=[],
    )
    simulation = Simulation(
        scenario_id="case",
        completed=True,
        transcript=[{"role": "agent", "message": "Wrong fare"}],
    )
    evaluation = Evaluation(
        scenario_id="case",
        scores=Scores(
            understanding=9,
            api_correctness=4,
            outcome_confirmation=9,
            naturalness=9,
        ),
        rationale="Fare calculation is incorrect",
        failures=[
            Failure(
                criterion="api_correctness",
                root_cause="code",
                quote="Wrong fare",
                explanation="The fare calculation returned an incorrect price",
                code_faults=[code_fault(path, function)],
            )
        ],
    )

    class Model:
        async def generate(self, model, instruction, data, schema, validate):
            validate(evaluation)
            return evaluation

    with pytest.raises(ValueError):
        asyncio.run(
            Evaluator(RefinementConfig(), Model()).run(
                scenario,
                simulation,
                "Prompt",
                {"backend/service.py": service_source()},
                {},
            )
        )


def test_fixer_rejects_patch_to_a_function_not_identified_by_evaluator():
    iteration = Iteration(
        number=1,
        evaluations=[
            Evaluation(
                scenario_id="case",
                scores=Scores(
                    understanding=9,
                    api_correctness=4,
                    outcome_confirmation=9,
                    naturalness=9,
                ),
                rationale="Wrong fare",
                failures=[
                    Failure(
                        criterion="api_correctness",
                        root_cause="code",
                        quote="Wrong fare",
                        explanation="Fare should be calculated correctly",
                        code_faults=[code_fault()],
                    )
                ],
            )
        ],
    )

    class Model:
        async def generate(self, model, instruction, data, schema, validate):
            assert data["code_faults"] == [code_fault().model_dump()]
            validate(
                Repair(
                    explanation="Unrelated edit",
                    system_prompt=None,
                    edits=[
                        FileEdit(
                            path="backend/service.py",
                            function="untouched",
                            old_text="return 99",
                            new_text="return 2",
                        )
                    ],
                )
            )

    with pytest.raises(ValueError, match="diagnosed"):
        asyncio.run(
            FixProposer(RefinementConfig(), Model()).run(
                iteration,
                "Prompt",
                {"backend/service.py": service_source()},
                {},
                [],
            )
        )
