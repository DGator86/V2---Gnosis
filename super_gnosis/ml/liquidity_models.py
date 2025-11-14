"""Liquidity engine model interfaces."""

from __future__ import annotations

from typing import Protocol, Any


class LiquidityModel(Protocol):
    """Protocol for liquidity engine models."""

    def predict(self, features: Any) -> Any:
        ...
