"""
Composer Agent v1.0

The central integrator that fuses signals from Hedge, Liquidity, and Sentiment agents
into a unified CompositeMarketDirective for the Trade Agent.

Core Responsibilities:
- Field fusion (confidence- and regime-weighted)
- Conflict resolution across engines
- Energy cost aggregation
- Expected move cone generation
- Trade style classification
- Rationale generation

Architecture:
- fusion/: Direction and confidence fusion logic
- energy/: Energy cost calculation and elasticity
- resolution/: Conflict resolution and regime weighting
- scenarios/: Expected move cone building
- classification/: Trade style determination
"""

from .composer_agent import ComposerAgent
from .schemas import (
    EngineDirective,
    CompositeMarketDirective,
    ExpectedMoveBand,
    ExpectedMoveCone,
    Direction,
)

__all__ = [
    "ComposerAgent",
    "EngineDirective",
    "CompositeMarketDirective",
    "ExpectedMoveBand",
    "ExpectedMoveCone",
    "Direction",
]
