"""Runtime settings and configurable quality/iteration limits."""

import tomllib
from pathlib import Path
from typing import Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PASS_SCORE = 8
MAX_ITERATIONS = 5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REFINER_", env_file=".env", extra="ignore", env_ignore_empty=True
    )

    api_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    artifacts_dir: Path = Path("artifacts")
    config_path: Path = Path("config/refinement.example.toml")
    elevenlabs_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="ELEVENLABS_API_KEY"
    )
    elevenlabs_agent_id: str = Field(default="", validation_alias="ELEVENLABS_AGENT_ID")
    agent_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="AGENT_API_KEY")
    model_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "REFINER_MODEL_API_KEY"),
    )
    model_base_url: HttpUrl = HttpUrl("https://api.anthropic.com/v1")
    test_database_url: SecretStr = Field(
        default=SecretStr(""), validation_alias="TEST_DATABASE_URL"
    )


class RefinementConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_score: int = Field(default=PASS_SCORE, ge=1, le=10)
    max_iterations: int = Field(default=MAX_ITERATIONS, ge=1)
    customer_model: str = "claude-haiku-5-5"
    evaluator_model: str = "claude-sonnet-5-5"
    repair_model: str = "claude-sonnet-5-5"
    model_max_tokens: int = Field(default=16384, ge=1)
    max_customer_turns: int = Field(default=18, ge=1, le=100)
    request_timeout_seconds: float = Field(default=120, gt=0)
    turn_timeout_seconds: float = Field(default=90, gt=0)
    transcript_timeout_seconds: float = Field(default=60, gt=0)
    readiness_timeout_seconds: float = Field(default=90, gt=0)
    command_timeout_seconds: float = Field(default=300, gt=0)
    model_attempts: int = Field(default=3, ge=1, le=5)
    workspace_root: Path = Path(".")
    scenarios_path: Path = Path("scenarios/airline.json")
    prompt_path: Path = Path("prompts/agent/system.md")
    knowledge_dir: Path = Path("knowledge")
    agent_branch_id: str | None = None
    editable_roots: list[str] = ["apps/api/src/airline_api"]
    max_patch_files: int = Field(default=6, ge=1, le=20)
    max_source_chars: int = Field(default=350_000, ge=1)
    verification_command: list[str] = ["uv", "run", "--all-packages", "pytest", "-q"]
    required_database_tests: list[str] = [
        "tests/test_bookings_api.py",
        "tests/test_flight_database.py",
        "tests/test_refinement.py::test_real_fixture_lifecycle_releases_inventory_between_iterations",
    ]
    reload_command: list[str] = [
        "uv",
        "run",
        "--package",
        "airline-refiner",
        "python",
        "-m",
        "airline_refiner.reload_service",
    ]

    @model_validator(mode="after")
    def require_commands(self) -> Self:
        for name in (
            "verification_command",
            "reload_command",
            "editable_roots",
            "required_database_tests",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} cannot be empty")
        return self


def load_config(path: Path) -> RefinementConfig:
    with path.open("rb") as handle:
        return RefinementConfig.model_validate(tomllib.load(handle))
