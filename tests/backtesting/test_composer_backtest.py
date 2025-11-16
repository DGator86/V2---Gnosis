# tests/backtesting/test_composer_backtest.py

from datetime import datetime, timedelta

import pandas as pd
import pytest

from backtesting.composer_backtest import BacktestConfig, run_composer_backtest
from schemas.core_schemas import EngineOutput
from engines.sentiment.models import SentimentEnvelope


class DummyHedgeEngine:
    def run(self, symbol, t):
        # Simple bullish bias increasing over time
        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=t,
            features={
                "net_pressure": 1e6,
                "movement_energy": 0.5,
                "elasticity": 1.0,
            },
            confidence=0.8,
            regime="normal",
        )


class DummyLiquidityEngine:
    def run(self, symbol, t):
        # Mild bullish or neutral depending on time; low friction
        return EngineOutput(
            kind="liquidity",
            symbol=symbol,
            timestamp=t,
            features={
                "polr_direction": 0.3,
                "polr_strength": 0.6,
                "liquidity_score": 0.9,
                "friction_cost": 0.2,
                "amihud_illiquidity": 1e-6,
            },
            confidence=0.8,
            regime="normal",
        )


class DummySentimentEngine:
    def process(self, symbol, t):
        # Slight bullish sentiment with moderate energy
        return SentimentEnvelope(
            bias="bullish",
            strength=0.7,
            energy=0.3,
            confidence=0.75,
            drivers={"wyckoff": 0.5, "flow": 0.3},
            timestamp=t,
            wyckoff_phase="markup",
        )


def _make_price_series(n: int = 10) -> pd.Series:
    """
    Create a simple upward-sloping price series.
    """
    base_time = pd.Timestamp(datetime(2024, 1, 1))
    times = [base_time + timedelta(days=i) for i in range(n)]
    prices = [100.0 + i for i in range(n)]  # 100, 101, 102, ...
    return pd.Series(prices, index=times)


def test_run_composer_backtest_basic(monkeypatch):
    symbol = "SPY"
    prices = _make_price_series(n=20)
    timestamps = prices.index.to_list()

    # Price getter: nearest previous
    def price_getter(sym: str, t: pd.Timestamp) -> float:
        assert sym == symbol
        return float(prices.loc[:t].iloc[-1])

    hedge_engine = DummyHedgeEngine()
    liq_engine = DummyLiquidityEngine()
    sent_engine = DummySentimentEngine()

    def hedge_runner(sym, t):
        return hedge_engine.run(sym, t)

    def liq_runner(sym, t):
        return liq_engine.run(sym, t)

    def sent_runner(sym, t):
        return sent_engine.process(sym, t)

    cfg = BacktestConfig(
        symbol=symbol,
        horizon_steps=1,
        notional=1.0,
    )

    result = run_composer_backtest(
        config=cfg,
        timestamps=timestamps,
        price_getter=price_getter,
        hedge_engine_runner=hedge_runner,
        liquidity_engine_runner=liq_runner,
        sentiment_engine_runner=sent_runner,
    )

    # Basic shape checks
    assert not result.log.empty
    # Because horizon=1, we lose the final bar
    assert len(result.log) == len(timestamps) - 1

    # Ensure columns exist
    for col in [
        "price",
        "future_price",
        "realized_return",
        "direction",
        "strength",
        "confidence",
        "energy_cost",
        "trade_style",
        "volatility",
    ]:
        assert col in result.log.columns

    # Metrics sanity
    assert 0.0 <= result.directional_accuracy <= 1.0
    # With an upward-sloping price series and bullish bias,
    # we expect positive PnL and positive Sharpe.
    assert result.naive_pnl > 0.0
    assert result.sharpe > 0.0

    # Energy-bucket accuracy dict should be non-empty and in [0,1]
    assert isinstance(result.energy_bucket_accuracy, dict)
    for v in result.energy_bucket_accuracy.values():
        assert 0.0 <= v <= 1.0


def test_run_composer_backtest_empty_prices():
    symbol = "SPY"
    prices = pd.Series(dtype=float)
    timestamps = []

    def price_getter(sym: str, t: pd.Timestamp) -> float:
        return float("nan")

    def dummy_runner(*args, **kwargs):
        return {}

    cfg = BacktestConfig(symbol=symbol, horizon_steps=1, notional=1.0)

    result = run_composer_backtest(
        config=cfg,
        timestamps=timestamps,
        price_getter=price_getter,
        hedge_engine_runner=dummy_runner,
        liquidity_engine_runner=dummy_runner,
        sentiment_engine_runner=dummy_runner,
    )

    assert result.log.empty
    assert result.directional_accuracy == 0.0
    assert result.naive_pnl == 0.0
    assert result.sharpe == 0.0
    assert result.energy_bucket_accuracy == {}
