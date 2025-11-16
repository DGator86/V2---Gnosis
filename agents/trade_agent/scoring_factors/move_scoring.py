# agents/trade_agent/scoring_factors/move_scoring.py

"""
Expected Move Fit Scorer

Scores how well a strategy aligns with the expected move magnitude.

Expected Move → Strategy Fit:
- SMALL: Favor condors, calendars, butterflies (range-bound)
- MEDIUM: Favor verticals, diagonals (moderate directional)
- LARGE: Favor outright long options (strong directional)
- EXPLOSIVE: Favor straddles, strangles (large moves either direction)

Strategy Characteristics:
- Capped structures (condors): Best for small moves
- Spreads: Good for medium moves
- Outright options: Best for large moves
- Straddles/strangles: Best for explosive moves (direction agnostic)
"""

from __future__ import annotations

from agents.trade_agent.schemas import ExpectedMove, StrategyType


class MoveScorer:
    """
    Scores strategy fit with expected move magnitude.
    Returns 0.0 - 1.0 score.
    """

    # Tiny expected move: favor ultra-tight range-bound structures
    TINY_MOVE_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.95,
        StrategyType.CALENDAR_SPREAD: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.75,
        StrategyType.CALL_DEBIT_SPREAD: 0.60,
        StrategyType.PUT_DEBIT_SPREAD: 0.60,
        StrategyType.STOCK: 0.50,
        StrategyType.SYNTHETIC_LONG: 0.45,
        StrategyType.SYNTHETIC_SHORT: 0.45,
        StrategyType.STRANGLE: 0.35,
        StrategyType.LONG_CALL: 0.30,
        StrategyType.LONG_PUT: 0.30,
        StrategyType.STRADDLE: 0.25,
        StrategyType.REVERSE_IRON_CONDOR: 0.20,
    }

    # Small expected move: favor range-bound structures
    SMALL_MOVE_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALENDAR_SPREAD: 0.95,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.80,
        StrategyType.CALL_DEBIT_SPREAD: 0.70,
        StrategyType.PUT_DEBIT_SPREAD: 0.70,
        StrategyType.STOCK: 0.60,
        StrategyType.SYNTHETIC_LONG: 0.55,
        StrategyType.SYNTHETIC_SHORT: 0.55,
        StrategyType.STRANGLE: 0.45,
        StrategyType.LONG_CALL: 0.40,
        StrategyType.LONG_PUT: 0.40,
        StrategyType.STRADDLE: 0.35,
        StrategyType.REVERSE_IRON_CONDOR: 0.30,
    }

    # Medium expected move: favor verticals and diagonals
    MEDIUM_MOVE_SCORES = {
        StrategyType.CALL_DEBIT_SPREAD: 1.0,
        StrategyType.PUT_DEBIT_SPREAD: 1.0,
        StrategyType.DIAGONAL_SPREAD: 0.95,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.85,
        StrategyType.STOCK: 0.80,
        StrategyType.LONG_CALL: 0.80,
        StrategyType.LONG_PUT: 0.80,
        StrategyType.SYNTHETIC_LONG: 0.75,
        StrategyType.SYNTHETIC_SHORT: 0.75,
        StrategyType.IRON_CONDOR: 0.65,
        StrategyType.CALENDAR_SPREAD: 0.65,
        StrategyType.STRANGLE: 0.60,
        StrategyType.STRADDLE: 0.55,
        StrategyType.REVERSE_IRON_CONDOR: 0.60,
    }

    # Large expected move: favor outright long options
    LARGE_MOVE_SCORES = {
        StrategyType.LONG_CALL: 1.0,
        StrategyType.LONG_PUT: 1.0,
        StrategyType.STOCK: 0.90,
        StrategyType.SYNTHETIC_LONG: 0.90,
        StrategyType.SYNTHETIC_SHORT: 0.90,
        StrategyType.STRADDLE: 0.85,
        StrategyType.STRANGLE: 0.80,
        StrategyType.CALL_DEBIT_SPREAD: 0.75,
        StrategyType.PUT_DEBIT_SPREAD: 0.75,
        StrategyType.REVERSE_IRON_CONDOR: 0.75,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.55,
        StrategyType.CALENDAR_SPREAD: 0.45,
        StrategyType.IRON_CONDOR: 0.30,
    }

    # Explosive expected move: favor straddles/strangles
    EXPLOSIVE_MOVE_SCORES = {
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 0.95,
        StrategyType.REVERSE_IRON_CONDOR: 0.90,
        StrategyType.LONG_CALL: 0.85,
        StrategyType.LONG_PUT: 0.85,
        StrategyType.STOCK: 0.75,
        StrategyType.SYNTHETIC_LONG: 0.75,
        StrategyType.SYNTHETIC_SHORT: 0.75,
        StrategyType.CALL_DEBIT_SPREAD: 0.65,
        StrategyType.PUT_DEBIT_SPREAD: 0.65,
        StrategyType.DIAGONAL_SPREAD: 0.55,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.45,
        StrategyType.CALENDAR_SPREAD: 0.35,
        StrategyType.IRON_CONDOR: 0.20,
    }

    @classmethod
    def score(
        cls,
        strategy_type: StrategyType,
        expected_move: ExpectedMove,
    ) -> float:
        """
        Return expected move fit score [0.0, 1.0].

        Args:
            strategy_type: The strategy being evaluated
            expected_move: Expected move magnitude

        Returns:
            Score from 0.0 (poor fit) to 1.0 (excellent fit)
        """
        if expected_move == ExpectedMove.EXPLOSIVE:
            return cls.EXPLOSIVE_MOVE_SCORES.get(strategy_type, 0.5)
        elif expected_move == ExpectedMove.LARGE:
            return cls.LARGE_MOVE_SCORES.get(strategy_type, 0.5)
        elif expected_move == ExpectedMove.MEDIUM:
            return cls.MEDIUM_MOVE_SCORES.get(strategy_type, 0.5)
        elif expected_move == ExpectedMove.SMALL:
            return cls.SMALL_MOVE_SCORES.get(strategy_type, 0.5)
        else:  # TINY
            return cls.TINY_MOVE_SCORES.get(strategy_type, 0.5)
