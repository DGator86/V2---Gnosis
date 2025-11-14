from __future__ import annotations

from typing import Optional
from core.schemas import (
    MarketTick,
    OrderFlowFeatures,
    ElasticityMetrics,
    LiquidityEngineSignals,
)
from ml.registry import ModelRegistry
from .base import BaseEngine


class LiquidityEngine(BaseEngine):
    """Builds liquidity map, price impact curve, and microstructure elasticity."""

    def __init__(self, model_registry: Optional[ModelRegistry] = None) -> None:
        self._model_registry = model_registry

    def name(self) -> str:
        return "liquidity_engine"

    def run(
        self,
        bar: MarketTick,
        order_flow: OrderFlowFeatures,
        elasticity: ElasticityMetrics,
    ) -> LiquidityEngineSignals:
        """
        Interpret order flow + elasticity into range, vacuums, and breakout vs
        mean-reversion probabilities.
        """
        # TODO: model usage
        return LiquidityEngineSignals(
            symbol=bar.symbol,
            timestamp=bar.timestamp,
            liquidity_zones={},
            vacuum_score=0.0,
            breakout_probability=0.3,
            mean_reversion_probability=0.7,
            elasticity=elasticity.dq_dp,
            confidence=0.3,
        )
