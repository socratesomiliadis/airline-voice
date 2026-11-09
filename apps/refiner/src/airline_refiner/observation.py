"""Publish durable, redacted snapshots while the autonomous loop runs."""

import asyncio
import difflib
import json
from datetime import UTC, datetime
from typing import Literal

from airline_contracts.monitoring import (
    IterationObservation,
    MessageObservation,
    RunObservation,
    RunStatus,
    ScenarioObservation,
    Stage,
    ToolObservation,
)

from airline_refiner.adapters.workspace import Artifacts
from airline_refiner.config import RefinementConfig
from airline_refiner.models import Evaluation, Repair, Scenario, Simulation


def now() -> datetime:
    return datetime.now(UTC)


class RunObserver:
    def __init__(self, run_id: str, config: RefinementConfig, artifacts: Artifacts) -> None:
        self.artifacts = artifacts
        timestamp = now()
        self.state = RunObservation(
            run_id=run_id,
            started_at=timestamp,
            updated_at=timestamp,
            heartbeat_at=timestamp,
            max_iterations=config.max_iterations,
            pass_score=config.pass_score,
        )
        self.publish()

    def publish(self) -> None:
        self.state.revision += 1
        self.state.updated_at = now()
        self.artifacts.write("monitor.json", self.state.model_dump(mode="json"))

    async def heartbeat(self) -> None:
        while True:
            await asyncio.sleep(5)
            self.state.heartbeat_at = now()
            self.publish()

    def start_iteration(self, number: int, scenarios: list[Scenario]) -> None:
        if self.state.iterations:
            self.state.iterations[-1].finished_at = now()
        self.state.iteration = number
        self.state.scenario_count = len(scenarios)
        self.state.iterations.append(
            IterationObservation(
                number=number,
                started_at=now(),
                scenarios=[
                    ScenarioObservation(id=scenario.id, goal=scenario.goal)
                    for scenario in scenarios
                ],
            )
        )
        self.phase("simulating")

    def phase(self, stage: Stage, scenario_id: str | None = None) -> None:
        self.state.stage = stage
        self.state.active_scenario = scenario_id
        if self.state.iterations:
            self.state.iterations[-1].stage = stage
            if scenario_id and stage in {"simulating", "evaluating"}:
                scenario = self.scenario(scenario_id)
                scenario.status = "simulating" if stage == "simulating" else "evaluating"
        self.publish()

    def scenario(self, scenario_id: str) -> ScenarioObservation:
        return next(s for s in self.state.iterations[-1].scenarios if s.id == scenario_id)

    def conversation(self, result: Simulation) -> None:
        scenario = self.scenario(result.scenario_id)
        scenario.conversation_id = result.conversation_id
        messages = []
        for index, message in enumerate(result.dialogue):
            role: Literal["user", "agent"] = "user" if message["role"] == "user" else "agent"
            timestamp = (
                scenario.dialogue[index].occurred_at if index < len(scenario.dialogue) else now()
            )
            messages.append(
                MessageObservation(role=role, message=message["message"], occurred_at=timestamp)
            )
        scenario.dialogue = messages
        tools: dict[str, ToolObservation] = {}
        for event in result.events:
            kind = event.get("type", "")
            if kind not in {
                "agent_tool_request",
                "agent_tool_response",
                "agent_tool_response_full_payload",
            }:
                continue
            data = event.get(kind, {})
            identifier = str(data.get("tool_call_id") or data.get("tool_name") or len(tools))
            status = (
                "running"
                if kind == "agent_tool_request"
                else ("error" if data.get("is_error") else data.get("status", "success"))
            )
            payload = data.get("full_tool_result")
            tools[identifier] = ToolObservation(
                id=identifier,
                name=data.get("tool_name", "Tool"),
                status=status,
                result=(payload if isinstance(payload, str) else json.dumps(payload))[:2000]
                if payload is not None
                else None,
            )
        scenario.tools = list(tools.values())
        scenario.errors = [
            *result.errors,
            *result.cleanup_errors,
            *(failure.evidence for failure in result.application_failures),
        ]
        self.publish()

    def evaluated(self, evaluation: Evaluation) -> None:
        scenario = self.scenario(evaluation.scenario_id)
        scenario.evaluation = evaluation.model_dump(mode="json")
        scenario.status = "passed" if evaluation.passes(self.state.pass_score) else "failed"
        self.publish()

    def proposed(self, repair: Repair, prompt: str) -> None:
        iteration = self.state.iterations[-1]
        iteration.change_status = "proposed"
        iteration.repair_explanation = repair.explanation
        if repair.system_prompt is not None:
            iteration.prompt_diff = "".join(
                difflib.unified_diff(
                    [line + "\n" for line in prompt.splitlines()],
                    [line + "\n" for line in repair.system_prompt.splitlines()],
                    fromfile="system.md (before)",
                    tofile="system.md (after)",
                )
            )
            self.artifacts.write_text(
                f"iteration-{iteration.number:02d}/prompt.patch", iteration.prompt_diff
            )
        self.publish()

    def patch(self, diff: str) -> None:
        self.state.iterations[-1].code_diff = diff
        self.publish()

    def repaired(self, error: str | None = None) -> None:
        iteration = self.state.iterations[-1]
        iteration.change_status = "rolled_back" if error else "applied"
        iteration.repair_error = error
        self.publish()

    def finish(self, status: RunStatus, error: str | None) -> None:
        self.state.status = status
        self.state.error = error
        self.state.heartbeat_at = now()
        if self.state.iterations:
            iteration = self.state.iterations[-1]
            iteration.finished_at = now()
            if status == "error" and iteration.change_status == "proposed":
                iteration.change_status = "recovery_failed"
                iteration.repair_error = error
        self.phase("error" if status == "error" else "completed")
