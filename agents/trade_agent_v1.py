from __future__ import annotations

"""Trade Agent v1.0 implementation skeleton."""

from typing import Any, Dict, List
from uuid import uuid4

from agents.base import TradeAgent
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from schemas.core_schemas import Suggestion, TradeIdea, TradeLeg


class TradeAgentV1(TradeAgent):
    """Map composer suggestions into concrete trade ideas."""

    def __init__(self, adapter: OptionsChainAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def generate_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        if suggestion.confidence < self.config.get("min_confidence", 0.5):
            return []

        trade_id = f"trade-{uuid4()}"
        leg = TradeLeg(instrument_type="STOCK", direction="buy", qty=1)
        idea = TradeIdea(
            id=trade_id,
            symbol=suggestion.symbol,
            strategy_type="long_stock" if suggestion.action == "long" else "short_stock",
            side="long" if suggestion.action == "long" else "short",
            legs=[leg],
            cost_per_unit=0.0,
            max_loss=0.0,
            max_profit=None,
            breakeven_levels=[],
            target_exit_price=None,
            stop_loss_price=None,
            recommended_units=1,
            confidence=suggestion.confidence,
            rationale=suggestion.reasoning,
            tags=suggestion.tags,
        )
        return [idea]
