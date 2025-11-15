from __future__ import annotations

"""Broker adapter interface."""

from typing import List, Protocol

from schemas.core_schemas import TradeIdea


class BrokerAdapter(Protocol):
    """Protocol describing broker interactions."""

    def place_trades(self, trades: List[TradeIdea]) -> None:
        """Place trades through the broker."""

        raise NotImplementedError
