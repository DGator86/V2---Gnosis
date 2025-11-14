"""Custom exceptions for Super Gnosis."""

from __future__ import annotations


class SuperGnosisError(Exception):
    """Base error for the Super Gnosis package."""


class ModelNotFoundError(SuperGnosisError):
    """Raised when a requested model is missing from the registry."""


class ConfigurationError(SuperGnosisError):
    """Raised when configuration cannot be loaded."""
