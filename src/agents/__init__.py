"""
Agent package initialization.
Provides analysis functions for all agents: hedge, liquidity, sentiment, composer.
"""

from .agent_hedge import analyze_hedge
from .agent_liquidity import analyze_liquidity
from .agent_sentiment import analyze_sentiment
from .agent_composer import compose_thesis

__all__ = [
    'analyze_hedge',
    'analyze_liquidity',
    'analyze_sentiment',
    'compose_thesis',
]
