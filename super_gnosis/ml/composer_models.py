"""Composer meta-model interfaces."""

from __future__ import annotations

from typing import Protocol, Any


class ComposerModel(Protocol):
    """Protocol for scenario composer models."""

    def predict(self, features: Any) -> Any:
        ...
