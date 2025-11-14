"""Config loader utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .config_models import AppConfig

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load the application configuration from YAML into typed models."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(raw)
