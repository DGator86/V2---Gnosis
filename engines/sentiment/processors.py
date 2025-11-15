from __future__ import annotations

"""Sentiment processor interfaces."""

from datetime import datetime
from typing import Protocol, Tuple

from engines.inputs.market_data_adapter import MarketDataAdapter
from engines.inputs.news_adapter import NewsAdapter


class SentimentProcessor(Protocol):
    """Protocol implemented by sentiment processors."""

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        """Return a sentiment score in [-1, 1] and a confidence in [0, 1]."""

        raise NotImplementedError


class NewsSentimentProcessor:
    """Placeholder news sentiment processor."""

    def __init__(self, adapter: NewsAdapter, config: dict) -> None:
        self.adapter = adapter
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        items = self.adapter.fetch_news(symbol, self.config.get("lookback_hours", 24), now)
        if not items:
            return 0.0, 0.0
        score = sum(1 for _ in items) / len(items)
        normalized_score = max(-1.0, min(1.0, score))
        return normalized_score, 0.5


class FlowSentimentProcessor:
    """Placeholder flow sentiment processor."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        return 0.0, 0.0


class TechnicalSentimentProcessor:
    """Technical sentiment derived from price indicators."""

    def __init__(self, market_adapter: MarketDataAdapter, config: dict) -> None:
        self.market_adapter = market_adapter
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        lookback = self.config.get("lookback", 14)
        data = self.market_adapter.fetch_ohlcv(symbol, lookback, now)
        if data.is_empty():
            return 0.0, 0.0
        returns = data["close"].pct_change().drop_nulls()
        score = float(returns.mean())
        normalized_score = max(-1.0, min(1.0, score * 100))
        return normalized_score, 0.5
