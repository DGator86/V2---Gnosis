# agents/trade_agent/ranking_engine.py

"""
Strategy Ranking Engine v1.0

The discriminatory layer that transforms "signal production" into "signal monetization."

This engine scores and ranks trade ideas across 7 dimensions:
1. Directional Congruence (25%)
2. Volatility Fit (20%)
3. Elasticity Alignment (15%)
4. Greek Alignment (15%)
5. Expected Move Fit (15%)
6. Capital Efficiency (10%)
7. Liquidity Penalty (multiplier)

Final Score Formula:
  score = (
      0.25 * direction_congruence
    + 0.20 * volatility_fit
    + 0.15 * elasticity_fit
    + 0.15 * greek_alignment
    + 0.15 * expected_move_fit
    + 0.10 * capital_efficiency
  ) * liquidity_score

All component scores: 0.0 - 1.0
Liquidity score: 0.0 - 1.0 (multiplier)

Output: Sorted list of TradeIdea with populated ranking_score

This engine determines which strategy to actually trade.
"""

from __future__ import annotations

from typing import List

from .schemas import ComposerTradeContext, TradeIdea
from .scoring_factors import (
    CapitalEfficiencyScorer,
    DirectionScorer,
    ElasticityScorer,
    GreekScorer,
    MoveScorer,
    VolScorer,
)


class StrategyRankingEngine:
    """
    Ranks trade ideas using multi-dimensional scoring.

    Usage:
        engine = StrategyRankingEngine()
        ranked_ideas = engine.rank(ideas, context)
    """

    # Scoring weights (must sum to 1.0)
    WEIGHT_DIRECTION = 0.25
    WEIGHT_VOLATILITY = 0.20
    WEIGHT_ELASTICITY = 0.15
    WEIGHT_GREEKS = 0.15
    WEIGHT_MOVE = 0.15
    WEIGHT_CAPITAL = 0.10

    def __init__(self):
        """Initialize scoring components."""
        self.direction_scorer = DirectionScorer()
        self.vol_scorer = VolScorer()
        self.elasticity_scorer = ElasticityScorer()
        self.greek_scorer = GreekScorer()
        self.move_scorer = MoveScorer()
        self.capital_scorer = CapitalEfficiencyScorer()

    def rank(
        self,
        ideas: List[TradeIdea],
        ctx: ComposerTradeContext,
        max_capital: float = 100_000.0,
    ) -> List[TradeIdea]:
        """
        Rank trade ideas by composite scoring.

        Args:
            ideas: List of TradeIdea objects (post-sizing)
            ctx: Composer trade context with market signals
            max_capital: Total available capital (for efficiency scoring)

        Returns:
            Sorted list of TradeIdea (descending ranking_score)
        """
        if not ideas:
            return []

        for idea in ideas:
            # Compute individual dimension scores
            direction_score = self.direction_scorer.score(
                idea.strategy_type,
                ctx.direction,
            )

            vol_score = self.vol_scorer.score(
                idea.strategy_type,
                ctx.volatility_regime,
            )

            elasticity_score = self.elasticity_scorer.score(
                idea.strategy_type,
                ctx.elastic_energy,
            )

            greek_score = self.greek_scorer.score(
                idea.strategy_type,
                ctx.gamma_exposure,
                ctx.vanna_exposure,
                ctx.charm_exposure,
            )

            move_score = self.move_scorer.score(
                idea.strategy_type,
                ctx.expected_move,
            )

            # Capital efficiency score
            max_risk = idea.max_risk or 0.0
            max_profit = idea.max_profit or 0.0
            sizing_fraction = max_risk / max_capital if max_capital > 0 else 0.0
            r_multiple = (
                max_profit / max_risk if max_risk > 0 else 0.0
            )

            capital_score = self.capital_scorer.score(
                r_multiple,
                sizing_fraction,
                max_risk,
                max_profit,
                max_capital,
            )

            # Composite weighted score
            composite = (
                self.WEIGHT_DIRECTION * direction_score
                + self.WEIGHT_VOLATILITY * vol_score
                + self.WEIGHT_ELASTICITY * elasticity_score
                + self.WEIGHT_GREEKS * greek_score
                + self.WEIGHT_MOVE * move_score
                + self.WEIGHT_CAPITAL * capital_score
            )

            # Liquidity penalty (multiplier)
            liquidity_multiplier = ctx.liquidity_score

            # Final score
            final_score = composite * liquidity_multiplier

            # Update idea
            idea.ranking_score = final_score

        # Sort descending by ranking_score
        sorted_ideas = sorted(
            ideas,
            key=lambda x: (x.ranking_score or 0.0),
            reverse=True,
        )

        return sorted_ideas

    def get_scoring_breakdown(
        self,
        idea: TradeIdea,
        ctx: ComposerTradeContext,
        max_capital: float = 100_000.0,
    ) -> dict:
        """
        Get detailed scoring breakdown for a single idea (debugging).

        Args:
            idea: TradeIdea to analyze
            ctx: Composer trade context
            max_capital: Total available capital

        Returns:
            Dictionary with individual dimension scores
        """
        direction_score = self.direction_scorer.score(
            idea.strategy_type,
            ctx.direction,
        )

        vol_score = self.vol_scorer.score(
            idea.strategy_type,
            ctx.volatility_regime,
        )

        elasticity_score = self.elasticity_scorer.score(
            idea.strategy_type,
            ctx.elastic_energy,
        )

        greek_score = self.greek_scorer.score(
            idea.strategy_type,
            ctx.gamma_exposure,
            ctx.vanna_exposure,
            ctx.charm_exposure,
        )

        move_score = self.move_scorer.score(
            idea.strategy_type,
            ctx.expected_move,
        )

        max_risk = idea.max_risk or 0.0
        max_profit = idea.max_profit or 0.0
        sizing_fraction = max_risk / max_capital if max_capital > 0 else 0.0
        r_multiple = max_profit / max_risk if max_risk > 0 else 0.0

        capital_score = self.capital_scorer.score(
            r_multiple,
            sizing_fraction,
            max_risk,
            max_profit,
            max_capital,
        )

        composite = (
            self.WEIGHT_DIRECTION * direction_score
            + self.WEIGHT_VOLATILITY * vol_score
            + self.WEIGHT_ELASTICITY * elasticity_score
            + self.WEIGHT_GREEKS * greek_score
            + self.WEIGHT_MOVE * move_score
            + self.WEIGHT_CAPITAL * capital_score
        )

        final_score = composite * ctx.liquidity_score

        return {
            "direction_score": direction_score,
            "vol_score": vol_score,
            "elasticity_score": elasticity_score,
            "greek_score": greek_score,
            "move_score": move_score,
            "capital_score": capital_score,
            "composite": composite,
            "liquidity_multiplier": ctx.liquidity_score,
            "final_score": final_score,
            "weights": {
                "direction": self.WEIGHT_DIRECTION,
                "volatility": self.WEIGHT_VOLATILITY,
                "elasticity": self.WEIGHT_ELASTICITY,
                "greeks": self.WEIGHT_GREEKS,
                "move": self.WEIGHT_MOVE,
                "capital": self.WEIGHT_CAPITAL,
            },
        }
