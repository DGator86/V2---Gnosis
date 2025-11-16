# agents/trade_agent/scoring_factors/capital_efficiency_scoring.py

"""
Capital Efficiency Scorer

Scores the capital efficiency of a strategy based on:
- R multiple (reward-to-risk ratio)
- Sizing fraction (Kelly allocation as % of capital)
- Cost efficiency (return per dollar at risk)

Capital Efficiency = R_multiple × sizing_fraction × cost_adjustment

Where:
- R_multiple: Expected reward-to-risk (from SizingEngine)
- sizing_fraction: Normalized Kelly fraction (0-1)
- cost_adjustment: Penalizes expensive strategies relative to capital at risk

This rewards strategies that offer:
- High payoff relative to risk
- Appropriate sizing (not too small, not hitting caps)
- Good return-on-capital efficiency
"""

from __future__ import annotations


class CapitalEfficiencyScorer:
    """
    Scores capital efficiency of a strategy.
    Returns 0.0 - 1.0 score.
    """

    @classmethod
    def score(
        cls,
        r_multiple: float,
        sizing_fraction: float,
        max_risk: float,
        max_profit: float,
        max_capital: float,
    ) -> float:
        """
        Return capital efficiency score [0.0, 1.0].

        Args:
            r_multiple: Expected reward-to-risk ratio
            sizing_fraction: Kelly fraction (capital at risk / max_capital)
            max_risk: Capital at risk for this idea
            max_profit: Expected max profit for this idea
            max_capital: Total available capital

        Returns:
            Score from 0.0 (poor efficiency) to 1.0 (excellent efficiency)
        """
        # Base efficiency: R multiple normalized to 0-1 range
        # Typical R multiples: 0.7 - 3.0, map to 0-1
        r_score = min(1.0, max(0.0, (r_multiple - 0.5) / 2.5))

        # Sizing score: prefer moderate sizing (not too small, not hitting caps)
        # Ideal sizing: 0.02 - 0.08 range (2-8% of capital)
        # Penalize very small (<1%) and very large (>10%) allocations
        if sizing_fraction < 0.01:
            sizing_score = sizing_fraction / 0.01  # Linear ramp up to 1%
        elif sizing_fraction > 0.10:
            sizing_score = max(0.5, 1.0 - (sizing_fraction - 0.10) / 0.10)
        else:
            # Sweet spot: 1-10%
            sizing_score = 1.0

        # Cost efficiency: return on capital at risk
        # High R multiple strategies with good sizing get boost
        if max_risk > 0:
            return_on_risk = max_profit / max_risk if max_profit > 0 else 0.0
            cost_score = min(1.0, return_on_risk / 3.0)  # Normalize to 3x
        else:
            cost_score = 0.0

        # Composite: weighted average
        composite = (
            0.40 * r_score +      # R multiple importance
            0.35 * sizing_score +  # Sizing appropriateness
            0.25 * cost_score      # Return efficiency
        )

        return max(0.0, min(1.0, composite))
