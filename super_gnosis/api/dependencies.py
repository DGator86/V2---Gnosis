"""Dependency wiring for the FastAPI application."""

from __future__ import annotations

from functools import lru_cache

from ml.registry import ModelRegistry


@lru_cache()
def get_model_registry() -> ModelRegistry:
    """Return a cached model registry instance."""

    return ModelRegistry()
