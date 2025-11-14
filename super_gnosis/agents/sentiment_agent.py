from __future__ import annotations

from core.schemas import SentimentEngineSignals, SentimentAgentPacket
from .base import BaseAgent


class SentimentAgent(BaseAgent):
    """Reduces sentiment engine output into clean bias and probabilities."""

    def name(self) -> str:
        return "sentiment_agent"

    def run(self, sent: SentimentEngineSignals) -> SentimentAgentPacket:
        return SentimentAgentPacket(
            symbol=sent.symbol,
            timestamp=sent.timestamp,
            trend_state=sent.trend_state,
            sentiment_bias=sent.sentiment_bias,
            compression_prob=sent.compression_prob,
            capitulation_prob=sent.capitulation_prob,
            trend_persistence_prob=sent.trend_persistence_prob,
            confidence=sent.confidence,
        )
