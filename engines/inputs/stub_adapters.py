"""In-memory stub adapters used for tests and demos."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import polars as pl

from .market_data_adapter import MarketDataAdapter
from .news_adapter import NewsAdapter
from .options_chain_adapter import OptionsChainAdapter


class StaticOptionsAdapter(OptionsChainAdapter):
    """Return a synthetic options chain centred around spot."""

    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:  # type: ignore[override]
        strikes = [90, 95, 100, 105, 110]
        expiries = [now.date(), (now + timedelta(days=7)).date(), (now + timedelta(days=30)).date()]
        rows: List[Dict[str, float | str]] = []
        for strike in strikes:
            for expiry in expiries:
                intrinsic = max(0.0, 100.0 - strike) if strike < 100 else max(0.0, strike - 100.0)
                mid = 1.0 + intrinsic / 10
                rows.append(
                    {
                        "symbol": symbol,
                        "strike": float(strike),
                        "expiry": expiry.isoformat(),
                        "gamma": 0.01 if strike == 100 else -0.005,
                        "vanna": 0.02,
                        "charm": -0.015,
                        "open_interest": 500,
                        "underlying_price": 100.0,
                        "option_type": "call" if strike >= 100 else "put",
                        "mid": mid,
                    }
                )
        return pl.DataFrame(rows)


class StaticMarketDataAdapter(MarketDataAdapter):
    """Provide deterministic OHLCV and trade data for tests."""

    def fetch_ohlcv(self, symbol: str, lookback: int, now: datetime) -> pl.DataFrame:  # type: ignore[override]
        base_price = 100.0
        data = {
            "timestamp": [now - timedelta(days=i) for i in range(lookback)][::-1],
            "open": [base_price + i * 0.1 for i in range(lookback)],
            "high": [base_price + i * 0.15 for i in range(lookback)],
            "low": [base_price + i * 0.05 for i in range(lookback)],
            "close": [base_price + i * 0.1 for i in range(lookback)],
            "volume": [1000 + i * 10 for i in range(lookback)],
        }
        return pl.DataFrame(data)

    def fetch_intraday_trades(self, symbol: str, lookback_minutes: int, now: datetime) -> pl.DataFrame:  # type: ignore[override]
        trades = {
            "timestamp": [now - timedelta(minutes=i * 5) for i in range(lookback_minutes // 5)],
            "price": [100 + i * 0.05 for i in range(lookback_minutes // 5)],
            "size": [10 + i for i in range(lookback_minutes // 5)],
            "side": ["buy" if i % 2 == 0 else "sell" for i in range(lookback_minutes // 5)],
        }
        return pl.DataFrame(trades)


class StaticNewsAdapter(NewsAdapter):
    """Return canned news items."""

    def fetch_news(self, symbol: str, lookback_hours: int, now: datetime) -> List[Dict[str, str]]:  # type: ignore[override]
        return [
            {"headline": f"{symbol} beats expectations", "sentiment": "positive"},
            {"headline": f"{symbol} faces regulatory review", "sentiment": "negative"},
        ]
