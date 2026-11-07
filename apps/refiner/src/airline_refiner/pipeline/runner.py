"""Autonomous simulate → evaluate → repair → reload/publish → repeat orchestration."""

import asyncio
import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter

from airline_refiner.adapters.api import AirlineAPI
from airline_refiner.adapters.elevenlabs import ElevenLabs
from airline_refiner.adapters.model import Model
from airline_refiner.adapters.workspace import Artifacts, Workspace, atomic_write
from airline_refiner.config import RefinementConfig
from airline_refiner.errors import RecoveryError, RefinementError
from airline_refiner.models import CodeFault, Iteration, Repair, RunResult, Scenario
from airline_refiner.observation import RunObserver
from airline_refiner.pipeline.stages.evaluate import Evaluator
from airline_refiner.pipeline.stages.propose import FixProposer
from airline_refiner.pipeline.stages.simulate import Simulator

logger = logging.getLogger(__name__)


def load_scenarios(path: Path) -> list[Scenario]:
    scenarios = TypeAdapter(list[Scenario]).validate_json(path.read_text())
    if not scenarios or len({scenario.id for scenario in scenarios}) != len(scenarios):
        raise RefinementError("Scenario suite must be nonempty with unique IDs")
    return scenarios


class RefinementRunner:
    def __init__(
        self,
        config: RefinementConfig,
        model: Model,
        provider: ElevenLabs,
        api: AirlineAPI,
        workspace: Workspace,
        artifacts: Artifacts,
    ) -> None:
        self.config, self.provider, self.api = config, provider, api
        self.workspace, self.artifacts = workspace, artifacts
        self.simulator = Simulator(config, model, provider, api)
        self.evaluator = Evaluator(config, model)
        self.proposer = FixProposer(config, model)
        self.observer: RunObserver | None = None

    async def apply_repair(
        self,
        repair: Repair,
        prompt: str,
        sources: dict[str, str],
        prefix: str,
        code_faults: list[CodeFault],
    ) -> str:
        transaction = self.workspace.plan(repair.edits, sources, code_faults)
        self.artifacts.write_text(prefix + "/code.patch", transaction.diff(self.workspace.root))
        if self.observer:
            self.observer.patch(transaction.diff(self.workspace.root))
        prompt_path = self.workspace.root / self.config.prompt_path
        local_prompt = prompt_path.read_text() if prompt_path.exists() else None
        code_applied, prompt_attempted = False, False
        try:
            if repair.edits:
                if self.observer:
                    self.observer.phase("verifying")
                transaction.apply()
                code_applied = True
                await self.workspace.command(
                    self.config.verification_command,
                    Path(prefix) / "verification.log",
                    self.artifacts,
                )
                if self.observer:
                    self.observer.phase("reloading")
                await self.workspace.command(
                    self.config.reload_command, Path(prefix) / "reload.log", self.artifacts
                )
                await self.api.ready(self.config.readiness_timeout_seconds)
            if repair.system_prompt is not None:
                if self.observer:
                    self.observer.phase("publishing")
                prompt_attempted = True
                await self.provider.update_prompt(repair.system_prompt)
                atomic_write(prompt_path, repair.system_prompt + "\n")
                prompt = repair.system_prompt
            return prompt
        except BaseException:
            if self.observer:
                self.observer.phase("rollback")
            try:
                if prompt_attempted:
                    # A timeout can mean the provider accepted the write: explicitly restore it.
                    await self.provider.update_prompt(prompt)
                    if local_prompt is None:
                        prompt_path.unlink(missing_ok=True)
                    else:
                        atomic_write(prompt_path, local_prompt)
                if code_applied:
                    transaction.rollback()
                    await self.workspace.command(
                        self.config.reload_command,
                        Path(prefix) / "rollback-reload.log",
                        self.artifacts,
                    )
                    await self.api.ready(self.config.readiness_timeout_seconds)
            except BaseException:
                # Always restore files even when provider or reload recovery is unavailable.
                transaction.rollback()
                raise RecoveryError(
                    "Repair rollback could not restore the running service/agent"
                ) from None
            raise

    async def run(self, run_id: str | None = None) -> RunResult:
        result = RunResult(
            run_id=run_id or uuid4().hex,
            status="error",
            pass_score=self.config.pass_score,
            max_iterations=self.config.max_iterations,
        )
        self.observer = RunObserver(result.run_id, self.config, self.artifacts)
        self.simulator.on_update = self.observer.conversation
        heartbeat = asyncio.create_task(self.observer.heartbeat())
        self.artifacts.write("configuration.json", self.config.model_dump(mode="json"))
        try:
            with self.workspace.lock():
                scenarios = load_scenarios(self.workspace.root / self.config.scenarios_path)
                knowledge: dict[str, Any] = {
                    path.name: json.loads(path.read_text())
                    for path in sorted(
                        (self.workspace.root / self.config.knowledge_dir).glob("*.json")
                    )
                }
                if not knowledge:
                    raise RefinementError("No policy documents found for grounded evaluation")
                sources = self.workspace.source()
                await self.api.ready(self.config.readiness_timeout_seconds)
                prompt = await self.provider.configure_chat()
                self.artifacts.write_text("initial-prompt.md", prompt)
                self.artifacts.write(
                    "scenarios.json", [s.model_dump(mode="json") for s in scenarios]
                )
                previous_errors: list[str] = []
                for number in range(1, self.config.max_iterations + 1):
                    self.observer.start_iteration(number, scenarios)
                    iteration = Iteration(number=number)
                    result.iterations.append(iteration)
                    prefix = f"iteration-{number:02d}"
                    self.artifacts.write_text(prefix + "/prompt.md", prompt)
                    self.artifacts.write(prefix + "/source.json", sources)
                    for scenario in scenarios:
                        logger.info(
                            "Iteration %d/%d: %s", number, self.config.max_iterations, scenario.id
                        )
                        caller = f"ref-{result.run_id[:12]}-{number}-{scenario.id}"[:100]
                        self.observer.phase("simulating", scenario.id)
                        simulation = await self.simulator.run(scenario, caller)
                        iteration.simulations.append(simulation)
                        self.artifacts.write(
                            prefix + f"/{scenario.id}.simulation.json",
                            simulation.model_dump(mode="json"),
                        )
                        self.observer.phase("evaluating", scenario.id)
                        evaluation = await self.evaluator.run(
                            scenario, simulation, prompt, sources, knowledge
                        )
                        iteration.evaluations.append(evaluation)
                        self.observer.evaluated(evaluation)
                        self.artifacts.write(
                            prefix + f"/{scenario.id}.evaluation.json",
                            evaluation.model_dump(mode="json"),
                        )
                        logger.info("Scores %s: %s", scenario.id, evaluation.scores.model_dump())
                        self.artifacts.write("run.json", result.model_dump(mode="json"))
                    if all(e.passes(self.config.pass_score) for e in iteration.evaluations):
                        result.status = "passed"
                        break
                    if number == self.config.max_iterations:
                        result.status = "iteration_limit"
                        break  # Never leave a final, unevaluated repair deployed.
                    try:
                        self.observer.phase("repairing")
                        repair = await self.proposer.run(
                            iteration, prompt, sources, knowledge, previous_errors
                        )
                        self.artifacts.write(
                            prefix + "/repair.json", repair.model_dump(mode="json")
                        )
                        self.observer.proposed(repair, prompt)
                        code_faults = [
                            fault
                            for evaluation in iteration.evaluations
                            for failure in evaluation.failures
                            for fault in failure.code_faults
                        ]
                        prompt = await self.apply_repair(
                            repair, prompt, sources, prefix, code_faults
                        )
                        iteration.repair_applied = True
                        self.observer.repaired()
                        sources = self.workspace.source()
                    except RecoveryError:
                        raise
                    except (RefinementError, OSError) as error:
                        message = (
                            str(error)
                            if isinstance(error, RefinementError)
                            else type(error).__name__
                        )
                        iteration.repair_error = message
                        self.observer.repaired(message)
                        logs = []
                        for name in ("verification.log", "reload.log"):
                            path = self.artifacts.directory / prefix / name
                            if path.exists():
                                logs.append(path.read_text()[-12_000:])
                        previous_errors.append(message + "\n" + "\n".join(logs))
                        logger.warning("Repair rejected and rolled back: %s", message)
                    self.artifacts.write(
                        prefix + "/iteration.json", iteration.model_dump(mode="json")
                    )
        except RefinementError as error:
            result.error = str(error)
            result.status = "error"
        except Exception as error:
            result.error = f"Refinement failed ({type(error).__name__})"
            result.status = "error"
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            self.observer.finish(result.status, result.error)
            self.artifacts.write("run.json", result.model_dump(mode="json"))
        return result
