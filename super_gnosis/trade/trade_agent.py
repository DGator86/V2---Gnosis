from __future__ import annotations

from typing import List
from core.schemas import MarketScenarioPacket, TradeIdea, TradeLeg


class TradeAgent:
    """
    Converts a MarketScenarioPacket into one or more trade ideas.
    No memory, no throttling – just mapping scenario → ideas.
    """

    def generate_trades(
        self,
        scenario: MarketScenarioPacket,
        max_risk_dollars: float,
    ) -> List[TradeIdea]:
        """
        Entry point for the Composer → TradeAgent handoff.

        Parameters
        ----------
        scenario: MarketScenarioPacket
            Current fused view of the market state.
        max_risk_dollars: float
            Max risk per trade idea (used to back into size).
        """
        # TODO: strategy selection + options chain integration
        leg = TradeLeg(
            side="buy",
            instrument_type="stock",
            symbol=scenario.symbol,
            quantity=1,
        )

        idea = TradeIdea(
            symbol=scenario.symbol,
            timestamp=scenario.timestamp,
            strategy_name="placeholder_stock_directional",
            scenario_label=scenario.scenario_label,
            legs=[leg],
            total_cost=100.0,
            max_loss=max_risk_dollars,
            max_profit=None,
            target_price=0.0,
            stop_price=0.0,
            projected_profit_at_target=0.0,
            probability_of_target=0.5,
            recommended_risk_fraction=0.01,
        )
        return [idea]
