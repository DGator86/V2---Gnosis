from __future__ import annotations

"""Sentiment Agent v1.0 implementation skeleton."""

from typing import Any, Dict
from uuid import uuid4

from agents.base import PrimaryAgent
from schemas.core_schemas import StandardSnapshot, Suggestion


class SentimentAgentV1(PrimaryAgent):
    """Interpret sentiment features."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        sentiment = snapshot.sentiment
        score = sentiment.get("sentiment_score", 0.0)
        confidence = sentiment.get("sentiment_confidence", 0.0)

        if score > self.config.get("bullish_threshold", 0.2):
            action = "long"
            tags = ["bullish_sentiment"]
            reasoning = "Positive sentiment"
        elif score < -self.config.get("bearish_threshold", 0.2):
            action = "short"
            tags = ["bearish_sentiment"]
            reasoning = "Negative sentiment"
        else:
            action = "flat"
            tags = ["mixed_sentiment"]
            reasoning = "Mixed sentiment"

        return Suggestion(
            id=f"sent-{uuid4()}",
            layer="primary_sentiment",
            symbol=snapshot.symbol,
            action=action,
            confidence=float(min(1.0, confidence)),
            forecast={},
            reasoning=reasoning,
            tags=tags,
        )
