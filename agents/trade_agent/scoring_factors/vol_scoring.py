# agents/trade_agent/scoring_factors/vol_scoring.py

"""
Volatility Regime Fit Scorer

Scores how well a strategy aligns with the current volatility regime.

Regime Logic:
- LOW_VOL: Favor debit structures (long options), avoid credit structures
- MID_VOL: Balanced, slight preference for defined risk
- HIGH_VOL: Favor credit spreads, avoid naked long options
- VOL_CRUSH: Favor iron condors, credit spreads, short premium
- VOL_EXPANSION: Favor long straddles/strangles, long convex structures

Vega Profile:
- Positive vega (long vol) benefits from vol expansion
- Negative vega (short vol) benefits from vol crush
"""

from __future__ import annotations

from agents.trade_agent.schemas import StrategyType, VolatilityRegime


class VolScorer:
    """
    Scores strategy fit with volatility regime.
    Returns 0.0 - 1.0 score.
    """

    # Strategy vega profiles (1.0 = max positive vega, 0.0 = max negative vega)
    VEGA_PROFILES = {
        # Long convex (positive vega)
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 1.0,
        StrategyType.LONG_CALL: 0.95,
        StrategyType.LONG_PUT: 0.95,
        StrategyType.REVERSE_IRON_CONDOR: 0.90,
        # Debit spreads (slightly positive vega)
        StrategyType.CALL_DEBIT_SPREAD: 0.60,
        StrategyType.PUT_DEBIT_SPREAD: 0.60,
        StrategyType.DIAGONAL_SPREAD: 0.55,
        StrategyType.CALENDAR_SPREAD: 0.50,
        # Neutral structures
        StrategyType.BROKEN_WING_BUTTERFLY: 0.45,
        StrategyType.STOCK: 0.40,
        StrategyType.SYNTHETIC_LONG: 0.40,
        StrategyType.SYNTHETIC_SHORT: 0.40,
        # Credit structures (negative vega)
        StrategyType.IRON_CONDOR: 0.10,
    }

    # Volatility regime preferences
    VOL_EXPANSION_SCORES = {
        # Favor long vega structures
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 0.95,
        StrategyType.REVERSE_IRON_CONDOR: 0.90,
        StrategyType.LONG_CALL: 0.85,
        StrategyType.LONG_PUT: 0.85,
        StrategyType.CALL_DEBIT_SPREAD: 0.70,
        StrategyType.PUT_DEBIT_SPREAD: 0.70,
        StrategyType.DIAGONAL_SPREAD: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.55,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.50,
        StrategyType.STOCK: 0.45,
        StrategyType.SYNTHETIC_LONG: 0.45,
        StrategyType.SYNTHETIC_SHORT: 0.45,
        StrategyType.IRON_CONDOR: 0.20,  # Anti-vol expansion
    }

    VOL_CRUSH_SCORES = {
        # Favor short vega structures
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALENDAR_SPREAD: 0.75,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.70,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.CALL_DEBIT_SPREAD: 0.55,
        StrategyType.PUT_DEBIT_SPREAD: 0.55,
        StrategyType.STOCK: 0.60,
        StrategyType.SYNTHETIC_LONG: 0.55,
        StrategyType.SYNTHETIC_SHORT: 0.55,
        StrategyType.STRANGLE: 0.30,
        StrategyType.STRADDLE: 0.25,
        StrategyType.LONG_CALL: 0.35,
        StrategyType.LONG_PUT: 0.35,
        StrategyType.REVERSE_IRON_CONDOR: 0.20,
    }

    HIGH_VOL_SCORES = {
        # High vol: favor defined risk, avoid expensive long options
        StrategyType.IRON_CONDOR: 0.90,
        StrategyType.CALL_DEBIT_SPREAD: 0.85,
        StrategyType.PUT_DEBIT_SPREAD: 0.85,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.80,
        StrategyType.DIAGONAL_SPREAD: 0.75,
        StrategyType.CALENDAR_SPREAD: 0.70,
        StrategyType.STOCK: 0.65,
        StrategyType.SYNTHETIC_LONG: 0.60,
        StrategyType.SYNTHETIC_SHORT: 0.60,
        StrategyType.STRANGLE: 0.50,
        StrategyType.STRADDLE: 0.45,
        StrategyType.LONG_CALL: 0.40,
        StrategyType.LONG_PUT: 0.40,
        StrategyType.REVERSE_IRON_CONDOR: 0.55,
    }

    LOW_VOL_SCORES = {
        # Low vol: favor cheap long options, avoid credit structures
        StrategyType.LONG_CALL: 1.0,
        StrategyType.LONG_PUT: 1.0,
        StrategyType.STRADDLE: 0.90,
        StrategyType.STRANGLE: 0.85,
        StrategyType.REVERSE_IRON_CONDOR: 0.80,
        StrategyType.CALL_DEBIT_SPREAD: 0.75,
        StrategyType.PUT_DEBIT_SPREAD: 0.75,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.STOCK: 0.60,
        StrategyType.SYNTHETIC_LONG: 0.60,
        StrategyType.SYNTHETIC_SHORT: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.55,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.50,
        StrategyType.IRON_CONDOR: 0.40,
    }

    MID_VOL_SCORES = {
        # Mid vol: balanced, slight preference for defined risk
        StrategyType.CALL_DEBIT_SPREAD: 0.90,
        StrategyType.PUT_DEBIT_SPREAD: 0.90,
        StrategyType.DIAGONAL_SPREAD: 0.85,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.80,
        StrategyType.IRON_CONDOR: 0.75,
        StrategyType.CALENDAR_SPREAD: 0.75,
        StrategyType.STOCK: 0.70,
        StrategyType.LONG_CALL: 0.70,
        StrategyType.LONG_PUT: 0.70,
        StrategyType.STRADDLE: 0.65,
        StrategyType.STRANGLE: 0.65,
        StrategyType.REVERSE_IRON_CONDOR: 0.65,
        StrategyType.SYNTHETIC_LONG: 0.65,
        StrategyType.SYNTHETIC_SHORT: 0.65,
    }

    @classmethod
    def score(
        cls,
        strategy_type: StrategyType,
        vol_regime: VolatilityRegime,
    ) -> float:
        """
        Return volatility fit score [0.0, 1.0].

        Args:
            strategy_type: The strategy being evaluated
            vol_regime: Current volatility regime

        Returns:
            Score from 0.0 (poor fit) to 1.0 (excellent fit)
        """
        if vol_regime == VolatilityRegime.VOL_EXPANSION:
            return cls.VOL_EXPANSION_SCORES.get(strategy_type, 0.5)
        elif vol_regime == VolatilityRegime.VOL_CRUSH:
            return cls.VOL_CRUSH_SCORES.get(strategy_type, 0.5)
        elif vol_regime == VolatilityRegime.HIGH:
            return cls.HIGH_VOL_SCORES.get(strategy_type, 0.5)
        elif vol_regime == VolatilityRegime.LOW:
            return cls.LOW_VOL_SCORES.get(strategy_type, 0.5)
        else:  # MID
            return cls.MID_VOL_SCORES.get(strategy_type, 0.5)
