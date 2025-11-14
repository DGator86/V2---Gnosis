"""Logging helpers for Super Gnosis."""

from __future__ import annotations

import logging
from typing import Optional

from .config import get_settings


def configure_logging(name: Optional[str] = None) -> logging.Logger:
    """Configure and return a logger with application defaults."""

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    return logging.getLogger(name or "super_gnosis")
