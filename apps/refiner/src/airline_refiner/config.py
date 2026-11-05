"""Worker process settings. Quality policies belong in future configuration schemas."""

from pathlib import Path

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REFINER_", env_file=".env", extra="ignore")

    api_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    artifacts_dir: Path = Path("artifacts")
    config_path: Path = Path("config/refinement.example.toml")
