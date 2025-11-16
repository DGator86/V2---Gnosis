# agents/trade_agent/scoring_factors/greek_scoring.py

"""
Greek Alignment Scorer

Scores how well a strategy aligns with the dealer Greek regime.

Gamma Exposure:
- Negative GEX (dealers short gamma): Market is unstable, favor convexity
- Positive GEX (dealers long gamma): Market is stable, favor income/neutral

Vanna Exposure:
- Negative vanna: Spot ↑ → vol ↓ (vol crush), favor short vol
- Positive vanna: Spot ↑ → vol ↑ (vol expansion), favor long vol

Charm Exposure:
- Negative charm: Time decay reduces dealer hedging → favor short-dated convex
- Positive charm: Time decay increases dealer hedging → favor longer-dated structures

Composite Greek Score:
  gamma_component = f(gamma_exposure, strategy)
  vanna_component = f(vanna_exposure, strategy)
  charm_component = f(charm_exposure, strategy)

  greek_score = 0.50 * gamma_component
              + 0.30 * vanna_component
              + 0.20 * charm_component
"""

from __future__ import annotations

from agents.trade_agent.schemas import StrategyType


class GreekScorer:
    """
    Scores strategy alignment with dealer Greek exposures.
    Returns 0.0 - 1.0 composite score.
    """

    # Negative gamma regime: favor convexity
    NEGATIVE_GAMMA_SCORES = {
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 0.95,
        StrategyType.LONG_CALL: 0.90,
        StrategyType.LONG_PUT: 0.90,
        StrategyType.REVERSE_IRON_CONDOR: 0.85,
        StrategyType.CALL_DEBIT_SPREAD: 0.70,
        StrategyType.PUT_DEBIT_SPREAD: 0.70,
        StrategyType.STOCK: 0.60,
        StrategyType.SYNTHETIC_LONG: 0.60,
        StrategyType.SYNTHETIC_SHORT: 0.60,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.55,
        StrategyType.IRON_CONDOR: 0.30,
    }

    # Positive gamma regime: favor income/neutral
    POSITIVE_GAMMA_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALENDAR_SPREAD: 0.85,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.80,
        StrategyType.DIAGONAL_SPREAD: 0.75,
        StrategyType.STOCK: 0.70,
        StrategyType.SYNTHETIC_LONG: 0.65,
        StrategyType.SYNTHETIC_SHORT: 0.65,
        StrategyType.CALL_DEBIT_SPREAD: 0.65,
        StrategyType.PUT_DEBIT_SPREAD: 0.65,
        StrategyType.STRANGLE: 0.50,
        StrategyType.LONG_CALL: 0.45,
        StrategyType.LONG_PUT: 0.45,
        StrategyType.STRADDLE: 0.40,
        StrategyType.REVERSE_IRON_CONDOR: 0.35,
    }

    # Negative vanna: vol crush likely, favor short vol
    NEGATIVE_VANNA_SCORES = {
        StrategyType.IRON_CONDOR: 1.0,
        StrategyType.CALENDAR_SPREAD: 0.80,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.75,
        StrategyType.DIAGONAL_SPREAD: 0.70,
        StrategyType.CALL_DEBIT_SPREAD: 0.65,
        StrategyType.PUT_DEBIT_SPREAD: 0.65,
        StrategyType.STOCK: 0.65,
        StrategyType.SYNTHETIC_LONG: 0.60,
        StrategyType.SYNTHETIC_SHORT: 0.60,
        StrategyType.STRANGLE: 0.45,
        StrategyType.STRADDLE: 0.40,
        StrategyType.LONG_CALL: 0.50,
        StrategyType.LONG_PUT: 0.50,
        StrategyType.REVERSE_IRON_CONDOR: 0.35,
    }

    # Positive vanna: vol expansion likely, favor long vol
    POSITIVE_VANNA_SCORES = {
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 0.95,
        StrategyType.LONG_CALL: 0.85,
        StrategyType.LONG_PUT: 0.85,
        StrategyType.REVERSE_IRON_CONDOR: 0.80,
        StrategyType.CALL_DEBIT_SPREAD: 0.70,
        StrategyType.PUT_DEBIT_SPREAD: 0.70,
        StrategyType.DIAGONAL_SPREAD: 0.65,
        StrategyType.STOCK: 0.60,
        StrategyType.SYNTHETIC_LONG: 0.60,
        StrategyType.SYNTHETIC_SHORT: 0.60,
        StrategyType.CALENDAR_SPREAD: 0.55,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.50,
        StrategyType.IRON_CONDOR: 0.40,
    }

    # Negative charm: favor short-dated convex
    NEGATIVE_CHARM_SCORES = {
        StrategyType.STRADDLE: 1.0,
        StrategyType.STRANGLE: 0.95,
        StrategyType.LONG_CALL: 0.90,
        StrategyType.LONG_PUT: 0.90,
        StrategyType.REVERSE_IRON_CONDOR: 0.80,
        StrategyType.CALL_DEBIT_SPREAD: 0.75,
        StrategyType.PUT_DEBIT_SPREAD: 0.75,
        StrategyType.STOCK: 0.65,
        StrategyType.SYNTHETIC_LONG: 0.65,
        StrategyType.SYNTHETIC_SHORT: 0.65,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.60,
        StrategyType.DIAGONAL_SPREAD: 0.55,
        StrategyType.CALENDAR_SPREAD: 0.50,
        StrategyType.IRON_CONDOR: 0.45,
    }

    # Positive charm: favor longer-dated structures
    POSITIVE_CHARM_SCORES = {
        StrategyType.CALENDAR_SPREAD: 1.0,
        StrategyType.DIAGONAL_SPREAD: 0.90,
        StrategyType.IRON_CONDOR: 0.85,
        StrategyType.BROKEN_WING_BUTTERFLY: 0.80,
        StrategyType.STOCK: 0.70,
        StrategyType.CALL_DEBIT_SPREAD: 0.70,
        StrategyType.PUT_DEBIT_SPREAD: 0.70,
        StrategyType.SYNTHETIC_LONG: 0.65,
        StrategyType.SYNTHETIC_SHORT: 0.65,
        StrategyType.LONG_CALL: 0.60,
        StrategyType.LONG_PUT: 0.60,
        StrategyType.STRANGLE: 0.55,
        StrategyType.STRADDLE: 0.50,
        StrategyType.REVERSE_IRON_CONDOR: 0.50,
    }

    @classmethod
    def score(
        cls,
        strategy_type: StrategyType,
        gamma_exposure: float,
        vanna_exposure: float,
        charm_exposure: float,
    ) -> float:
        """
        Return composite Greek alignment score [0.0, 1.0].

        Args:
            strategy_type: The strategy being evaluated
            gamma_exposure: Dealer gamma exposure (negative = unstable)
            vanna_exposure: Dealer vanna exposure (negative = vol crush bias)
            charm_exposure: Dealer charm exposure (negative = decay bias)

        Returns:
            Composite score from 0.0 (poor fit) to 1.0 (excellent fit)
        """
        # Gamma component (50% weight)
        if gamma_exposure < 0:
            gamma_score = cls.NEGATIVE_GAMMA_SCORES.get(strategy_type, 0.5)
        else:
            gamma_score = cls.POSITIVE_GAMMA_SCORES.get(strategy_type, 0.5)

        # Vanna component (30% weight)
        if vanna_exposure < 0:
            vanna_score = cls.NEGATIVE_VANNA_SCORES.get(strategy_type, 0.5)
        else:
            vanna_score = cls.POSITIVE_VANNA_SCORES.get(strategy_type, 0.5)

        # Charm component (20% weight)
        if charm_exposure < 0:
            charm_score = cls.NEGATIVE_CHARM_SCORES.get(strategy_type, 0.5)
        else:
            charm_score = cls.POSITIVE_CHARM_SCORES.get(strategy_type, 0.5)

        # Composite weighted score
        composite = (
            0.50 * gamma_score + 0.30 * vanna_score + 0.20 * charm_score
        )

        return composite
