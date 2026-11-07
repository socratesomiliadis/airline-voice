"""Run the autonomous worker; help never starts provider calls or mutates code."""

import argparse
import asyncio
import logging
import shutil
from contextlib import AsyncExitStack
from pathlib import Path
from uuid import uuid4

import httpx

from airline_refiner.adapters.api import AirlineAPI
from airline_refiner.adapters.elevenlabs import ElevenLabs
from airline_refiner.adapters.model import JsonModel
from airline_refiner.adapters.workspace import Artifacts, Workspace
from airline_refiner.config import RefinementConfig, Settings, load_config
from airline_refiner.errors import RefinementError
from airline_refiner.pipeline.runner import RefinementRunner


def preflight(settings: Settings, config: RefinementConfig) -> None:
    missing = []
    for name, value in (
        ("ELEVENLABS_API_KEY", settings.elevenlabs_api_key.get_secret_value()),
        ("ELEVENLABS_AGENT_ID", settings.elevenlabs_agent_id),
        ("ANTHROPIC_API_KEY (or REFINER_MODEL_API_KEY)", settings.model_api_key.get_secret_value()),
    ):
        if not value:
            missing.append(name)
    if missing:
        raise RefinementError("Missing configuration: " + ", ".join(missing))
    for command in (config.verification_command, config.reload_command):
        if not shutil.which(command[0]):
            raise RefinementError(f"Configured command is not available on PATH: {command[0]}")


async def execute(settings: Settings, config: RefinementConfig) -> int:
    preflight(settings, config)
    run_id = uuid4().hex
    artifacts = Artifacts(
        settings.artifacts_dir / run_id,
        [
            settings.elevenlabs_api_key.get_secret_value(),
            settings.model_api_key.get_secret_value(),
            settings.agent_api_key.get_secret_value(),
        ],
    )
    async with AsyncExitStack() as stack:
        model_client = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url=str(settings.model_base_url).rstrip("/") + "/",
                headers={
                    "x-api-key": settings.model_api_key.get_secret_value(),
                    "anthropic-version": "2026-10-21",
                },
                timeout=config.request_timeout_seconds,
            )
        )
        provider_client = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url="https://api.elevenlabs.io/v1/",
                headers={"xi-api-key": settings.elevenlabs_api_key.get_secret_value()},
                timeout=config.request_timeout_seconds,
            )
        )
        api_client = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url=str(settings.api_base_url).rstrip("/") + "/",
                headers={"X-Agent-Api-Key": settings.agent_api_key.get_secret_value()},
                timeout=config.request_timeout_seconds,
            )
        )
        runner = RefinementRunner(
            config,
            JsonModel(model_client, config.model_attempts, config.model_max_tokens),
            ElevenLabs(provider_client, settings.elevenlabs_agent_id, config.agent_branch_id),
            AirlineAPI(api_client),
            Workspace(config),
            artifacts,
        )
        result = await runner.run(run_id)
    print(f"{result.status}: {len(result.iterations)} iterations; artifacts: {artifacts.directory}")
    if result.error:
        print(artifacts.redact(result.error))
    return {"passed": 0, "iteration_limit": 1, "error": 2}[result.status]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="airline-refiner",
        description="Autonomously simulate, evaluate, and refine an ElevenLabs airline agent.",
    )
    parser.add_argument("command", choices=["run"], nargs="?")
    parser.add_argument("--config", type=Path, help="TOML configuration path")
    parser.add_argument(
        "--max-iterations", type=int, help="Override the iteration limit (default 5)"
    )
    parser.add_argument(
        "--pass-score", type=int, help="Override every criterion's threshold (default 8)"
    )
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # HTTP debug/info logs can include signed URLs and are deliberately not emitted.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings()
        values = load_config(args.config or settings.config_path).model_dump()
        if args.max_iterations is not None:
            values["max_iterations"] = args.max_iterations
        if args.pass_score is not None:
            values["pass_score"] = args.pass_score
        config = RefinementConfig.model_validate(values)
        raise SystemExit(asyncio.run(execute(settings, config)))
    except RefinementError as error:
        parser.exit(2, str(error) + "\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Invalid refinement configuration ({type(error).__name__})\n")
    except KeyboardInterrupt:
        parser.exit(130, "Refinement interrupted\n")
