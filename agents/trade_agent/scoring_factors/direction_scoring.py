# agents/trade_agent/scoring_factors/direction_scoring.py

"""
Directional Congruence Scorer

Scores how well a strategy aligns with the market direction signal.

Bullish Hierarchy (descending preference):
  long_call > call_debit_spread > diagonal_spread > broken_wing_butterfly > straddle

Bearish Hierarchy (descending preference):
  long_put > put_debit_spread > diagonal_spread > broken_wing_butterfly > straddle

Neutral Hierarchy (descending preference):
  iron_condor > calendar_spread > broken_wing_butterfly > strangle

Convex strategies (straddle/strangle) score mid-range in directional markets
but high in uncertain/explosive conditions (handled by move_scoring).
"""

from __future__ import annotations

from agents.trade_agent.schemas import Direction, StrategyType


class DirectionScorer:
    """
    Scores strategy alignment with market direction.
    Returns 0.0 - 1.0 score.
    """

    # Bullish strategy scores (1.0 = perfect alignment)
    BULLISH_SCORES = {
        StrategyType.LONG_CALL: 1.0,
        StrategyType.CALL_DEBIT_SPREAD: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.75,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.70,
        StrategyType.STOCK: 0.85,
        StrategyType.SYNTHETIC_LONG: 0.80,
        StrategyType.STRADDLE: 0.50,  # Direction-neutral
        StrategyType.STRANGLE: 0.50,
        StrategyType.REVERSE_IRON_CONDOR: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.45,
        StrategyType.IRON_CONDOR: 0.30,  # Anti-directional
        StrategyType.LONG_PUT: 0.20,
        StrategyType.PUT_DEBIT_SPREAD: 0.25,
        StrategyType.SYNTHETIC_SHORT: 0.20,
    }

    # Bearish strategy scores
    BEARISH_SCORES = {
        StrategyType.LONG_PUT: 1.0,
        StrategyType.PUT_DEBIT_SPREAD: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.75,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.70,
        StrategyType.SYNTHETIC_SHORT: 0.80,
        StrategyType.STRADDLE: 0.50,  # Direction-neutral
        StrategyType.STRANGLE: 0.50,
        StrategyType.REVERSE_IRON_CONDOR: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.45,
        StrategyType.IRON_CONDOR: 0.30,  # Anti-directional
        StrategyType.LONG_CALL: 0.20,
        StrategyType.CALL_DEBIT_SPREAD: 0.25,
        StrategyType.STOCK: 0.15,
        StrategyType.SYNTHETIC_LONG: 0.20,
    }

    # Neutral strategy scores (prefer range-bound strategies)
    NEUTRAL_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALENDAR_SPREAD: 0.90,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.85,
        StrategyType.STRANGLE: 0.75,
        StrategyType.STRADDLE: 0.70,
        StrategyType.DIAGONAL_SPREAD: 0.60,
        StrategyType.REVERSE_IRON_CONDOR: 0.50,
        StrategyType.LONG_CALL: 0.40,
        StrategyType.LONG_PUT: 0.40,
        StrategyType.CALL_DEBIT_SPREAD: 0.45,
        StrategyType.PUT_DEBIT_SPREAD: 0.45,
        StrategyType.STOCK: 0.35,
        StrategyType.SYNTHETIC_LONG: 0.30,
        StrategyType.SYNTHETIC_SHORT: 0.30,
    }

    @classmethod
    def score(
        cls,
        strategy_type: StrategyType,
        direction: Direction,
    ) -> float:
        """
        Return directional congruence score [0.0, 1.0].

        Args:
            strategy_type: The strategy being evaluated
            direction: Market direction signal

        Returns:
            Score from 0.0 (misaligned) to 1.0 (perfect alignment)
        """
        if direction == Direction.BULLISH:
            return cls.BULLISH_SCORES.get(strategy_type, 0.5)
        elif direction == Direction.BEARISH:
            return cls.BEARISH_SCORES.get(strategy_type, 0.5)
        else:  # NEUTRAL
            return cls.NEUTRAL_SCORES.get(strategy_type, 0.5)
