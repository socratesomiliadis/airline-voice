"""Environment-backed settings; provider credentials stay server-side."""

from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://airline:airline_local@localhost:5432/airline"
    )
    cors_origins: list[str] = ["http://localhost:3000"]
    agent_api_key: SecretStr | None = None
    knowledge_dir: Path = Path("knowledge")
    refiner_artifacts_dir: Path = Path("artifacts")
    simulation_now: AwareDatetime | None = None
