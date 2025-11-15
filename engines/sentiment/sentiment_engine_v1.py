from __future__ import annotations

"""Sentiment Engine v1.0 implementation skeleton."""

from datetime import datetime
from typing import Any, Dict, List, Tuple

from engines.base import Engine
from engines.sentiment.processors import SentimentProcessor
from schemas.core_schemas import EngineOutput


class SentimentEngineV1(Engine):
    """Fuse multiple sentiment processors into a single output."""

    def __init__(self, processors: List[SentimentProcessor], config: Dict[str, Any]) -> None:
        self.processors = processors
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        scores: List[Tuple[float, float]] = [processor.compute(symbol, now) for processor in self.processors]
        total_weight = sum(conf for _, conf in scores)

        if total_weight == 0:
            features: Dict[str, float] = {
                "sentiment_score": 0.0,
                "sentiment_confidence": 0.0,
                "news_sentiment_score": 0.0,
                "flow_sentiment_score": 0.0,
                "technical_sentiment_score": 0.0,
                "sentiment_energy": 0.0,
            }
            regime = "quiet"
        else:
            weighted_score = sum(score * conf for score, conf in scores) / total_weight
            weighted_score = max(-1.0, min(1.0, weighted_score))
            features = {
                "sentiment_score": float(weighted_score),
                "sentiment_confidence": float(min(1.0, total_weight / len(scores))),
                "sentiment_energy": float(abs(weighted_score) * min(1.0, total_weight / len(scores))),
                "news_sentiment_score": float(scores[0][0]) if len(scores) > 0 else 0.0,
                "flow_sentiment_score": float(scores[1][0]) if len(scores) > 1 else 0.0,
                "technical_sentiment_score": float(scores[2][0]) if len(scores) > 2 else 0.0,
            }
            regime = self._determine_regime(features)

        return EngineOutput(
            kind="sentiment",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=features.get("sentiment_confidence", 0.0),
            regime=regime,
        )

    def _determine_regime(self, features: Dict[str, float]) -> str:
        score = features.get("sentiment_score", 0.0)
        if score > self.config.get("bullish_threshold", 0.3):
            return "bullish_news"
        if score < -self.config.get("bearish_threshold", 0.3):
            return "bearish_news"
        if features.get("sentiment_confidence", 0.0) < 0.2:
            return "quiet"
        return "mixed"
