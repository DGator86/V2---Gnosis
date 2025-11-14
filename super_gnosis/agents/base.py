from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from core.schemas import (
    HedgeEngineSignals,
    LiquidityEngineSignals,
    SentimentEngineSignals,
    HedgeAgentPacket,
    LiquidityAgentPacket,
    SentimentAgentPacket,
)


class BaseAgent(ABC):
    """Base class for agents. Stateless interpreters over engine outputs."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def run(self, *args, **kwargs):
        """Transform engine signals into reduced agent packet."""
