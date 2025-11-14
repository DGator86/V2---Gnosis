"""Sentiment engine model interfaces."""

from __future__ import annotations

from typing import Protocol, Any


class SentimentModel(Protocol):
    """Protocol for sentiment engine models."""

    def predict(self, features: Any) -> Any:
        ...
