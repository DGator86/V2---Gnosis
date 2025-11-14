from __future__ import annotations

from core.schemas import HedgeEngineSignals, HedgeAgentPacket
from .base import BaseAgent


class HedgeAgent(BaseAgent):
    """Reduces hedge engine signal into a decision-ready summary."""

    def name(self) -> str:
        return "hedge_agent"

    def run(self, hedge: HedgeEngineSignals) -> HedgeAgentPacket:
        """
        Map field thrust, stability, and jump risk into simplified directional
        bias and thrust energy.
        """
        return HedgeAgentPacket(
            symbol=hedge.symbol,
            timestamp=hedge.timestamp,
            bias=hedge.directional_bias,
            thrust_energy=hedge.field_thrust,
            field_stability=hedge.field_stability,
            jump_risk_score=hedge.jump_risk_score,
            confidence=hedge.confidence,
        )
