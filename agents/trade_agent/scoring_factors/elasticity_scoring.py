# agents/trade_agent/scoring_factors/elasticity_scoring.py

"""
Elasticity / Energy Alignment Scorer

Scores how well a strategy aligns with the elastic energy regime.

Elastic Energy = internal "cost" to move price.

High Energy (>1.5):
  - Price is difficult to move
  - Favor defined risk structures (spreads, condors)
  - Avoid expensive convex plays (long straddles)
  - Reward capital-efficient strategies

Low Energy (<0.75):
  - Price is easy to move
  - Favor convex plays (long calls/puts, straddles)
  - Reward unlimited upside structures
  - Avoid capped structures (condors)

Medium Energy (0.75-1.5):
  - Balanced regime
  - All strategies viable
"""

from __future__ import annotations

from agents.trade_agent.schemas import StrategyType


class ElasticityScorer:
    """
    Scores strategy fit with elastic energy regime.
    Returns 0.0 - 1.0 score.
    """

    # High energy regime (>1.5): favor defined risk, capital-efficient
    HIGH_ENERGY_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALL_DEBIT_SPREAD: 0.95,
        StrategyType.PUT_DEBIT_SPREAD: 0.95,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.85,
        StrategyType.CALENDAR_SPREAD: 0.80,
        StrategyType.STOCK: 0.75,
        StrategyType.SYNTHETIC_LONG: 0.70,
        StrategyType.SYNTHETIC_SHORT: 0.70,
        StrategyType.STRANGLE: 0.50,
        StrategyType.REVERSE_IRON_CONDOR: 0.45,
        StrategyType.LONG_CALL: 0.40,
        StrategyType.LONG_PUT: 0.40,
        StrategyType.STRADDLE: 0.35,
    }

    # Low energy regime (<0.75): favor convex, unlimited upside
    LOW_ENERGY_SCORES = {
        StrategyType.LONG_CALL: 1.0,
        StrategyType.LONG_PUT: 1.0,
        StrategyType.STRADDLE: 0.95,
        StrategyType.STRANGLE: 0.90,
        StrategyType.REVERSE_IRON_CONDOR: 0.85,
        StrategyType.CALL_DEBIT_SPREAD: 0.75,
        StrategyType.PUT_DEBIT_SPREAD: 0.75,
        StrategyType.STOCK: 0.70,
        StrategyType.SYNTHETIC_LONG: 0.70,
        StrategyType.SYNTHETIC_SHORT: 0.70,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.55,
        StrategyType.IRON_CONDOR: 0.40,
    }

    # Medium energy (0.75-1.5): balanced
    MEDIUM_ENERGY_SCORES = {
        StrategyType.CALL_DEBIT_SPREAD: 0.90,
        StrategyType.PUT_DEBIT_SPREAD: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.85,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.85,
        StrategyType.LONG_CALL: 0.80,
        StrategyType.LONG_PUT: 0.80,
        StrategyType.STOCK: 0.80,
        StrategyType.IRON_CONDOR: 0.75,
        StrategyType.CALENDAR_SPREAD: 0.75,
        StrategyType.STRADDLE: 0.75,
        StrategyType.STRANGLE: 0.75,
        StrategyType.REVERSE_IRON_CONDOR: 0.70,
        StrategyType.SYNTHETIC_LONG: 0.70,
        StrategyType.SYNTHETIC_SHORT: 0.70,
    }

    @classmethod
    def score(
        cls,
        strategy_type: StrategyType,
        elastic_energy: float,
    ) -> float:
        """
        Return elasticity fit score [0.0, 1.0].

        Args:
            strategy_type: The strategy being evaluated
            elastic_energy: Elastic energy scalar (typically 0.5 - 3.0)

        Returns:
            Score from 0.0 (poor fit) to 1.0 (excellent fit)
        """
        if elastic_energy > 1.5:
            # High energy: difficult to move
            return cls.HIGH_ENERGY_SCORES.get(strategy_type, 0.5)
        elif elastic_energy < 0.75:
            # Low energy: easy to move
            return cls.LOW_ENERGY_SCORES.get(strategy_type, 0.5)
        else:
            # Medium energy: balanced
            return cls.MEDIUM_ENERGY_SCORES.get(strategy_type, 0.5)
