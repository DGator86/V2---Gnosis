"""Hedge engine model interfaces."""

from __future__ import annotations

from typing import Protocol, Any


class HedgeModel(Protocol):
    """Protocol for hedge engine models."""

    def predict(self, features: Any) -> Any:
        ...
