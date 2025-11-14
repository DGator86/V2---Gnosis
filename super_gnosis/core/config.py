"""Configuration primitives for Super Gnosis."""

from __future__ import annotations

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    environment: str = Field("development", description="Deployment environment name")
    log_level: str = Field("INFO", description="Default logging level")

    class Config:
        env_prefix = "SUPER_GNOSIS_"
        case_sensitive = False


def get_settings() -> Settings:
    """Return application settings instance."""

    return Settings()
