from __future__ import annotations

"""Primary agent interfaces for the Super Gnosis pipeline."""

from typing import List, Protocol

from schemas.core_schemas import StandardSnapshot, Suggestion, TradeIdea


class PrimaryAgent(Protocol):
    """Protocol implemented by primary agents."""

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        """Produce a :class:`Suggestion` from ``snapshot``."""

        raise NotImplementedError


class ComposerAgent(Protocol):
    """Protocol for the composer agent."""

    def compose(self, snapshot: StandardSnapshot, suggestions: List[Suggestion]) -> Suggestion:
        """Combine primary suggestions into a composite suggestion."""

        raise NotImplementedError


class TradeAgent(Protocol):
    """Protocol for trade agents."""

    def generate_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        """Generate trade ideas from the composite suggestion."""

        raise NotImplementedError
