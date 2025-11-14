from __future__ import annotations

from typing import Optional
from core.schemas import (
    MarketTick,
    TechnicalFeatures,
    SentimentEngineSignals,
)
from ml.registry import ModelRegistry
from .base import BaseEngine


class SentimentEngine(BaseEngine):
    """Interprets indicators + behavioral data into sentiment/regime."""

    def __init__(self, model_registry: Optional[ModelRegistry] = None) -> None:
        self._model_registry = model_registry

    def name(self) -> str:
        return "sentiment_engine"

    def run(
        self,
        bar: MarketTick,
        technical: TechnicalFeatures,
    ) -> SentimentEngineSignals:
        """
        Use technical indicators and other features to infer trend state,
        behavioral bias, trend persistence, and squeeze/capitulation probabilities.
        """
        # TODO: ML integration
        return SentimentEngineSignals(
            symbol=bar.symbol,
            timestamp=bar.timestamp,
            trend_state="unknown",
            sentiment_bias="mixed",
            trend_persistence_prob=0.5,
            capitulation_prob=0.05,
            accumulation_prob=0.05,
            compression_prob=technical.compression_score,
            confidence=0.3,
        )
