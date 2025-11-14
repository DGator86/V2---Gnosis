from __future__ import annotations

from core.schemas import LiquidityEngineSignals, LiquidityAgentPacket
from .base import BaseAgent


class LiquidityAgent(BaseAgent):
    """Reduces liquidity signals into range and energy-to-cross."""

    def name(self) -> str:
        return "liquidity_agent"

    def run(self, liq: LiquidityEngineSignals) -> LiquidityAgentPacket:
        zones = liq.liquidity_zones
        range_low = zones.get("support", 0.0)
        range_high = zones.get("resistance", 0.0)
        span = max(range_high - range_low, 1e-6)

        energy_to_cross = span * liq.elasticity

        breakout_bias = "none"
        if liq.breakout_probability > 0.6:
            breakout_bias = "up"
        elif liq.mean_reversion_probability < 0.4:
            breakout_bias = "down"

        return LiquidityAgentPacket(
            symbol=liq.symbol,
            timestamp=liq.timestamp,
            range_low=range_low,
            range_high=range_high,
            vacuum_zones=[],
            breakout_bias=breakout_bias,
            energy_to_cross_range=energy_to_cross,
            confidence=liq.confidence,
        )
