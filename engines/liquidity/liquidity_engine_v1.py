from __future__ import annotations

"""Liquidity Engine v1.0 implementation skeleton."""

from datetime import datetime
from typing import Any, Dict

import polars as pl

from engines.base import Engine
from engines.inputs.market_data_adapter import MarketDataAdapter
from schemas.core_schemas import EngineOutput


class LiquidityEngineV1(Engine):
    """Compute liquidity diagnostics for a symbol."""

    def __init__(self, adapter: MarketDataAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        ohlcv = self.adapter.fetch_ohlcv(symbol, self.config.get("lookback", 30), now)
        trades = self.adapter.fetch_intraday_trades(symbol, self.config.get("intraday_minutes", 60), now)

        if ohlcv.is_empty():
            return EngineOutput(
                kind="liquidity",
                symbol=symbol,
                timestamp=now,
                features={},
                confidence=0.0,
                regime="thin_liquidity",
                metadata={"degraded": "no_ohlcv"},
            )

        features = self._compute_features(ohlcv, trades)
        regime = self._determine_regime(features)
        confidence = 1.0 if features else 0.0

        return EngineOutput(
            kind="liquidity",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=confidence,
            regime=regime,
        )

    def _compute_features(self, ohlcv: pl.DataFrame, trades: pl.DataFrame) -> Dict[str, float]:
        returns = ohlcv["close"].pct_change().fill_null(0.0)
        volume_series = ohlcv["volume"].cast(pl.Float64)
        volumes = volume_series.replace(0, None)

        amihud = float((returns.abs() / volumes).mean()) if volumes.is_not_null().any() else 0.0
        price_change = ohlcv["close"].diff().fill_null(0.0)

        signed_volume = pl.Series("signed_volume", [0.0])
        if not trades.is_empty():
            if "side" in trades.columns:
                sign = trades["side"].map_elements(lambda s: 1 if s == "buy" else -1)
                signed_volume = trades["size"] * sign
            else:
                signed_volume = trades.get_column("size")

        avg_signed_volume = float(signed_volume.abs().mean() or 1.0)
        kyle_lambda = float(price_change.abs().mean() / (avg_signed_volume + 1e-9))

        ofi = 0.0
        if not trades.is_empty() and "side" in trades.columns:
            buy_volume = trades.filter(pl.col("side") == "buy")["size"].sum()
            sell_volume = trades.filter(pl.col("side") == "sell")["size"].sum()
            denom = buy_volume + sell_volume
            ofi = float((buy_volume - sell_volume) / denom) if denom else 0.0

        vwap = float((ohlcv["close"] * ohlcv["volume"]).sum() / max(ohlcv["volume"].sum(), 1))
        close = float(ohlcv["close"].tail(1)[0])
        volume_profile_magnet = abs(close - vwap) / max(close, 1e-6)

        volume_std = volume_series.rolling_std(5, min_samples=1).fill_null(0.0)
        avg_volume = float(volume_series.mean() or 0.0)
        liquidity_void = float((volume_std > avg_volume).mean())

        avg_spread_bps = float(abs(price_change).mean() / max(close, 1e-6) * 10_000)

        return {
            "amihud_illiquidity": float(amihud),
            "kyle_lambda": float(kyle_lambda),
            "ofi": float(ofi),
            "volume_profile_magnet_score": float(volume_profile_magnet),
            "liquidity_void_score": float(liquidity_void),
            "avg_spread_bps": float(avg_spread_bps),
        }

    def _determine_regime(self, features: Dict[str, float]) -> str:
        if not features:
            return "thin_liquidity"
        if features["ofi"] > 0.6:
            return "one_sided_flow"
        if features["amihud_illiquidity"] > self.config.get("thin_threshold", 0.001):
            return "thin_liquidity"
        if features["amihud_illiquidity"] < self.config.get("high_threshold", 0.0001):
            return "high_liquidity"
        return "normal"
