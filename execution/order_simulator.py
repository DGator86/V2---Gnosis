from __future__ import annotations

"""Order simulator for backtesting."""

from typing import List

from schemas.core_schemas import TradeIdea


class OrderSimulator:
    """Simulate order fills and slippage."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def simulate_fills(self, trades: List[TradeIdea]) -> None:
        """Placeholder fill simulation."""

        for trade in trades:
            _ = trade
