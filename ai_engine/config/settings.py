"""Central configuration for the ARGUS-X AI engine.

All settings come from environment variables (optionally via a .env file).
Nothing secret is ever hardcoded here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    model_path: Path = Field(default=Path("models/anomaly_model.joblib"))
    model_version: str = Field(default="1.0.0")
    model_metadata_path: Path = Field(default=Path("models/model_metadata.json"))
    risk_config_path: Path = Field(default=Path("ai_engine/config/risk_config.yaml"))

    database_url: Optional[str] = Field(default=None)

    enable_llm_explanation: bool = Field(default=False)
    llm_api_key: Optional[str] = Field(default=None)
    llm_base_url: Optional[str] = Field(default=None)
    llm_model: Optional[str] = Field(default=None)

    log_level: str = Field(default="INFO")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()