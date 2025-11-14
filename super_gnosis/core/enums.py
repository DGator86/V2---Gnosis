"""Enum definitions used across Super Gnosis."""

from __future__ import annotations

from enum import Enum


class Environment(str, Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
