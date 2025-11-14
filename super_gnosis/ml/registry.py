from __future__ import annotations

from typing import Any, Dict

from core.exceptions import ModelNotFoundError


class ModelRegistry:
    """
    Thin wrapper around your ML models. Engines and Composer only see this
    interface, never model internals.
    """

    def __init__(self) -> None:
        self._models: Dict[str, Any] = {}

    def register_model(self, name: str, model: Any) -> None:
        """Register a preloaded model under a name."""

        self._models[name] = model

    def get_model(self, name: str) -> Any:
        """Retrieve a model by name; raise if missing."""

        try:
            return self._models[name]
        except KeyError as exc:
            raise ModelNotFoundError(f"Model '{name}' not found in registry") from exc
