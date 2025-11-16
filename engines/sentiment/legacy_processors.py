from __future__ import annotations

"""Sentiment processor interfaces."""

from datetime import datetime
from math import tanh
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
        sentiment_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
        values = [sentiment_map.get(item.get("sentiment", "neutral"), 0.0) for item in items]
        avg_score = sum(values) / len(values)
        normalized_score = float(max(-1.0, min(1.0, avg_score)))
        confidence = float(min(1.0, len(items) / 10))
        return normalized_score, confidence


class FlowSentimentProcessor:
    """Placeholder flow sentiment processor."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        bias = float(self.config.get("flow_bias", 0.0))
        confidence = float(min(1.0, abs(bias)))
        return max(-1.0, min(1.0, bias)), confidence


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
        momentum = float(returns.tail(lookback // 2).sum())
        normalized_score = float(max(-1.0, min(1.0, tanh(momentum * 10))))
        confidence = float(min(1.0, returns.len() / max(1, lookback)))
        return normalized_score, confidence
