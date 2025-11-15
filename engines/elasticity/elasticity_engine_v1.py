from __future__ import annotations

"""Elasticity Engine v1.0 implementation skeleton."""

from datetime import datetime
from typing import Any, Dict

from engines.base import Engine
from engines.inputs.market_data_adapter import MarketDataAdapter
from schemas.core_schemas import EngineOutput


class ElasticityEngineV1(Engine):
    """Estimate the energy required to move price."""

    def __init__(self, market_adapter: MarketDataAdapter, config: Dict[str, Any]) -> None:
        self.market_adapter = market_adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        ohlcv = self.market_adapter.fetch_ohlcv(symbol, self.config.get("lookback", 30), now)
        if ohlcv.is_empty():
            return EngineOutput(
                kind="elasticity",
                symbol=symbol,
                timestamp=now,
                features={},
                confidence=0.0,
                regime="low_resistance",
                metadata={"degraded": "no_data"},
            )

        returns = ohlcv["close"].pct_change().fill_null(0.0)
        vol = float(returns.std())
        avg_volume = float(ohlcv["volume"].mean() or 0.0)
        baseline = float(self.config.get("baseline_move_cost", 1.0))

        energy_up = baseline * (1 + max(0.0, vol)) * (1 + 1 / max(avg_volume, 1.0))
        energy_down = baseline * (1 + max(0.0, vol)) * (1 + 1 / max(avg_volume, 1.0))
        elasticity_up = 1 / max(energy_up, 1e-6)
        elasticity_down = 1 / max(energy_down, 1e-6)
        expected_move_cost = baseline * vol * 100

        features = {
            "energy_to_move_1pct_up": float(energy_up),
            "energy_to_move_1pct_down": float(energy_down),
            "elasticity_up": float(elasticity_up),
            "elasticity_down": float(elasticity_down),
            "expected_move_cost_1d": float(expected_move_cost),
        }

        regime = "high_resistance" if energy_up > baseline else "low_resistance"

        return EngineOutput(
            kind="elasticity",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=float(min(1.0, avg_volume / 10_000)),
            regime=regime,
        )
