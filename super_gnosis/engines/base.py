from __future__ import annotations

from abc import ABC, abstractmethod
from core.schemas import (
    MarketTick,
    OptionsSnapshot,
    TechnicalFeatures,
    OrderFlowFeatures,
    ElasticityMetrics,
    HedgeEngineSignals,
    LiquidityEngineSignals,
    SentimentEngineSignals,
    StandardizedSignals,
)


class BaseEngine(ABC):
    """Base class for all engines. Stateless, pure functions over inputs."""

    @abstractmethod
    def name(self) -> str:
        """Return the engine name."""

    @abstractmethod
    def run(self, *args, **kwargs):
        """Execute engine logic and return engine-specific signals."""
