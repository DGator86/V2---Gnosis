"""Sentiment Engine - Processor implementations."""

# New v1.0 full processors
from .all_processors import (
    BreadthRegimeProcessor,
    EnergyProcessor,
    FlowBiasProcessor,
    OscillatorProcessor,
    VolatilityProcessor,
    WyckoffProcessor,
)

# Legacy stub processors for backward compatibility
from ..legacy_processors import (
    FlowSentimentProcessor,
    NewsSentimentProcessor,
    SentimentProcessor,
    TechnicalSentimentProcessor,
)

__all__ = [
    # New v1.0 processors
    "WyckoffProcessor",
    "OscillatorProcessor",
    "VolatilityProcessor",
    "FlowBiasProcessor",
    "BreadthRegimeProcessor",
    "EnergyProcessor",
    # Legacy stub processors
    "SentimentProcessor",
    "FlowSentimentProcessor",
    "NewsSentimentProcessor",
    "TechnicalSentimentProcessor",
]
