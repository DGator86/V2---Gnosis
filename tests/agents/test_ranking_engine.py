# tests/agents/test_ranking_engine.py

"""
Comprehensive test suite for Phase 6: Strategy Ranking Engine v1.0

Tests cover:
1. Individual scoring factors (direction, vol, elasticity, Greeks, move, capital)
2. Composite scoring and weighting
3. Regime-specific strategy preferences
4. Edge cases and boundary conditions
5. Deterministic ranking and stability
"""

from __future__ import annotations

import pytest

from agents.trade_agent.ranking_engine import StrategyRankingEngine
from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    StrategyType,
    Timeframe,
    TradeIdea,
    VolatilityRegime,
)
from agents.trade_agent.scoring_factors import (
    CapitalEfficiencyScorer,
    DirectionScorer,
    ElasticityScorer,
    GreekScorer,
    MoveScorer,
    VolScorer,
)


def _ctx(
    direction: Direction = Direction.BULLISH,
    confidence: float = 0.7,
    expected_move: ExpectedMove = ExpectedMove.MEDIUM,
    vol_regime: VolatilityRegime = VolatilityRegime.MID,
    elastic_energy: float = 1.0,
    gamma: float = 0.0,
    vanna: float = 0.0,
    charm: float = 0.0,
    liquidity: float = 0.9,
) -> ComposerTradeContext:
    """Helper to create test context."""
    return ComposerTradeContext(
        asset="SPY",
        direction=direction,
        confidence=confidence,
        expected_move=expected_move,
        volatility_regime=vol_regime,
        timeframe=Timeframe.SWING,
        elastic_energy=elastic_energy,
        gamma_exposure=gamma,
        vanna_exposure=vanna,
        charm_exposure=charm,
        liquidity_score=liquidity,
    )


def _idea(
    strategy: StrategyType,
    max_risk: float = 1000.0,
    max_profit: float = 1500.0,
) -> TradeIdea:
    """Helper to create test idea."""
    return TradeIdea(
        asset="SPY",
        strategy_type=strategy,
        description="test",
        legs=[],
        max_risk=max_risk,
        max_profit=max_profit,
        recommended_size=1,
    )


# ============================================================================
# Test Individual Scoring Factors
# ============================================================================


class TestDirectionScorer:
    """Test directional congruence scoring."""

    def test_bullish_prefers_long_call(self):
        score_call = DirectionScorer.score(StrategyType.LONG_CALL, Direction.BULLISH)
        score_put = DirectionScorer.score(StrategyType.LONG_PUT, Direction.BULLISH)
        assert score_call > score_put

    def test_bearish_prefers_long_put(self):
        score_put = DirectionScorer.score(StrategyType.LONG_PUT, Direction.BEARISH)
        score_call = DirectionScorer.score(StrategyType.LONG_CALL, Direction.BEARISH)
        assert score_put > score_call

    def test_neutral_prefers_iron_condor(self):
        score_condor = DirectionScorer.score(StrategyType.IRON_CONDOR, Direction.NEUTRAL)
        score_call = DirectionScorer.score(StrategyType.LONG_CALL, Direction.NEUTRAL)
        assert score_condor > score_call

    def test_straddle_scores_mid_range_in_directional_markets(self):
        score_bullish = DirectionScorer.score(StrategyType.STRADDLE, Direction.BULLISH)
        score_bearish = DirectionScorer.score(StrategyType.STRADDLE, Direction.BEARISH)
        # Straddles are direction-neutral, should score ~0.5
        assert 0.4 <= score_bullish <= 0.6
        assert 0.4 <= score_bearish <= 0.6


class TestVolScorer:
    """Test volatility regime fit scoring."""

    def test_vol_expansion_prefers_long_vega(self):
        score_straddle = VolScorer.score(
            StrategyType.STRADDLE, VolatilityRegime.VOL_EXPANSION
        )
        score_condor = VolScorer.score(
            StrategyType.IRON_CONDOR, VolatilityRegime.VOL_EXPANSION
        )
        assert score_straddle > score_condor

    def test_vol_crush_prefers_short_vega(self):
        score_condor = VolScorer.score(
            StrategyType.IRON_CONDOR, VolatilityRegime.VOL_CRUSH
        )
        score_straddle = VolScorer.score(
            StrategyType.STRADDLE, VolatilityRegime.VOL_CRUSH
        )
        assert score_condor > score_straddle

    def test_high_vol_prefers_defined_risk(self):
        score_spread = VolScorer.score(
            StrategyType.CALL_DEBIT_SPREAD, VolatilityRegime.HIGH
        )
        score_long = VolScorer.score(
            StrategyType.LONG_CALL, VolatilityRegime.HIGH
        )
        assert score_spread > score_long

    def test_low_vol_prefers_long_options(self):
        score_long = VolScorer.score(
            StrategyType.LONG_CALL, VolatilityRegime.LOW
        )
        score_condor = VolScorer.score(
            StrategyType.IRON_CONDOR, VolatilityRegime.LOW
        )
        assert score_long > score_condor


class TestElasticityScorer:
    """Test elasticity/energy alignment scoring."""

    def test_high_energy_prefers_defined_risk(self):
        score_condor = ElasticityScorer.score(StrategyType.IRON_CONDOR, elastic_energy=2.5)
        score_straddle = ElasticityScorer.score(StrategyType.STRADDLE, elastic_energy=2.5)
        assert score_condor > score_straddle

    def test_low_energy_prefers_convex(self):
        score_long = ElasticityScorer.score(StrategyType.LONG_CALL, elastic_energy=0.5)
        score_condor = ElasticityScorer.score(StrategyType.IRON_CONDOR, elastic_energy=0.5)
        assert score_long > score_condor

    def test_medium_energy_is_balanced(self):
        score_spread = ElasticityScorer.score(
            StrategyType.CALL_DEBIT_SPREAD, elastic_energy=1.0
        )
        score_long = ElasticityScorer.score(StrategyType.LONG_CALL, elastic_energy=1.0)
        # Both should score reasonably well
        assert score_spread >= 0.7
        assert score_long >= 0.7


class TestGreekScorer:
    """Test dealer Greek alignment scoring."""

    def test_negative_gamma_prefers_convex(self):
        score_straddle = GreekScorer.score(
            StrategyType.STRADDLE, gamma_exposure=-2.0, vanna_exposure=0.0, charm_exposure=0.0
        )
        score_condor = GreekScorer.score(
            StrategyType.IRON_CONDOR, gamma_exposure=-2.0, vanna_exposure=0.0, charm_exposure=0.0
        )
        assert score_straddle > score_condor

    def test_positive_gamma_prefers_income(self):
        score_condor = GreekScorer.score(
            StrategyType.IRON_CONDOR, gamma_exposure=2.0, vanna_exposure=0.0, charm_exposure=0.0
        )
        score_straddle = GreekScorer.score(
            StrategyType.STRADDLE, gamma_exposure=2.0, vanna_exposure=0.0, charm_exposure=0.0
        )
        assert score_condor > score_straddle

    def test_negative_vanna_prefers_short_vol(self):
        score_condor = GreekScorer.score(
            StrategyType.IRON_CONDOR, gamma_exposure=0.0, vanna_exposure=-1.0, charm_exposure=0.0
        )
        score_straddle = GreekScorer.score(
            StrategyType.STRADDLE, gamma_exposure=0.0, vanna_exposure=-1.0, charm_exposure=0.0
        )
        assert score_condor > score_straddle

    def test_positive_vanna_prefers_long_vol(self):
        # Use stronger vanna signal to overcome gamma neutrality
        score_straddle = GreekScorer.score(
            StrategyType.STRADDLE, gamma_exposure=-1.0, vanna_exposure=1.0, charm_exposure=0.0
        )
        score_condor = GreekScorer.score(
            StrategyType.IRON_CONDOR, gamma_exposure=-1.0, vanna_exposure=1.0, charm_exposure=0.0
        )
        # With negative gamma + positive vanna, straddle should win
        assert score_straddle > score_condor


class TestMoveScorer:
    """Test expected move fit scoring."""

    def test_tiny_move_prefers_condors(self):
        score_condor = MoveScorer.score(StrategyType.IRON_CONDOR, ExpectedMove.TINY)
        score_straddle = MoveScorer.score(StrategyType.STRADDLE, ExpectedMove.TINY)
        assert score_condor > score_straddle

    def test_small_move_prefers_range_bound(self):
        score_condor = MoveScorer.score(StrategyType.IRON_CONDOR, ExpectedMove.SMALL)
        score_long = MoveScorer.score(StrategyType.LONG_CALL, ExpectedMove.SMALL)
        assert score_condor > score_long

    def test_medium_move_prefers_verticals(self):
        score_spread = MoveScorer.score(StrategyType.CALL_DEBIT_SPREAD, ExpectedMove.MEDIUM)
        score_condor = MoveScorer.score(StrategyType.IRON_CONDOR, ExpectedMove.MEDIUM)
        assert score_spread > score_condor

    def test_large_move_prefers_outright(self):
        score_long = MoveScorer.score(StrategyType.LONG_CALL, ExpectedMove.LARGE)
        score_condor = MoveScorer.score(StrategyType.IRON_CONDOR, ExpectedMove.LARGE)
        assert score_long > score_condor

    def test_explosive_move_prefers_straddles(self):
        score_straddle = MoveScorer.score(StrategyType.STRADDLE, ExpectedMove.EXPLOSIVE)
        score_condor = MoveScorer.score(StrategyType.IRON_CONDOR, ExpectedMove.EXPLOSIVE)
        assert score_straddle > score_condor


class TestCapitalEfficiencyScorer:
    """Test capital efficiency scoring."""

    def test_higher_r_multiple_scores_higher(self):
        # High R multiple (3.0x)
        score_high = CapitalEfficiencyScorer.score(
            r_multiple=3.0,
            sizing_fraction=0.05,
            max_risk=5000.0,
            max_profit=15000.0,
            max_capital=100_000.0,
        )
        # Low R multiple (1.0x)
        score_low = CapitalEfficiencyScorer.score(
            r_multiple=1.0,
            sizing_fraction=0.05,
            max_risk=5000.0,
            max_profit=5000.0,
            max_capital=100_000.0,
        )
        assert score_high > score_low

    def test_appropriate_sizing_scores_well(self):
        # Ideal sizing (5%)
        score_ideal = CapitalEfficiencyScorer.score(
            r_multiple=1.5,
            sizing_fraction=0.05,
            max_risk=5000.0,
            max_profit=7500.0,
            max_capital=100_000.0,
        )
        # Too small (0.5%)
        score_small = CapitalEfficiencyScorer.score(
            r_multiple=1.5,
            sizing_fraction=0.005,
            max_risk=500.0,
            max_profit=750.0,
            max_capital=100_000.0,
        )
        assert score_ideal > score_small

    def test_zero_risk_returns_low_score(self):
        score = CapitalEfficiencyScorer.score(
            r_multiple=1.5,
            sizing_fraction=0.0,
            max_risk=0.0,
            max_profit=0.0,
            max_capital=100_000.0,
        )
        # Zero risk should produce very low score (but not necessarily zero due to r_score component)
        assert score < 0.3


# ============================================================================
# Test Composite Ranking Engine
# ============================================================================


class TestStrategyRankingEngine:
    """Test full ranking engine integration."""

    def test_ranking_engine_ranks_all_ideas(self):
        engine = StrategyRankingEngine()
        ctx = _ctx()

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        ranked = engine.rank(ideas, ctx)

        # All ideas should have ranking scores
        assert all(idea.ranking_score is not None for idea in ranked)
        # Should be sorted descending
        scores = [idea.ranking_score for idea in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_bullish_large_move_prefers_long_call(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(direction=Direction.BULLISH, expected_move=ExpectedMove.LARGE)

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        ranked = engine.rank(ideas, ctx)

        # Long call should rank highest
        assert ranked[0].strategy_type == StrategyType.LONG_CALL

    def test_neutral_small_move_prefers_iron_condor(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(direction=Direction.NEUTRAL, expected_move=ExpectedMove.SMALL)

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        ranked = engine.rank(ideas, ctx)

        # Iron condor should rank highest
        assert ranked[0].strategy_type == StrategyType.IRON_CONDOR

    def test_vol_expansion_negative_gamma_prefers_straddle(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(
            direction=Direction.NEUTRAL,
            expected_move=ExpectedMove.EXPLOSIVE,
            vol_regime=VolatilityRegime.VOL_EXPANSION,
            gamma=-2.0,
        )

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        ranked = engine.rank(ideas, ctx)

        # Straddle should rank highest (vol expansion + negative gamma + explosive move)
        assert ranked[0].strategy_type == StrategyType.STRADDLE

    def test_liquidity_penalty_affects_ranking(self):
        engine = StrategyRankingEngine()

        # High liquidity
        ctx_high_liq = _ctx(liquidity=0.9)
        # Low liquidity
        ctx_low_liq = _ctx(liquidity=0.3)

        # Need separate idea objects to avoid reference issues
        idea_high = _idea(StrategyType.LONG_CALL)
        idea_low = _idea(StrategyType.LONG_CALL)

        ranked_high = engine.rank([idea_high], ctx_high_liq)
        ranked_low = engine.rank([idea_low], ctx_low_liq)

        # Higher liquidity should produce higher score
        assert ranked_high[0].ranking_score > ranked_low[0].ranking_score

    def test_identical_conditions_produce_deterministic_ranking(self):
        engine = StrategyRankingEngine()
        ctx = _ctx()

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        # Run twice
        ranked1 = engine.rank(ideas.copy(), ctx)
        ranked2 = engine.rank(ideas.copy(), ctx)

        # Scores should be identical
        scores1 = [idea.ranking_score for idea in ranked1]
        scores2 = [idea.ranking_score for idea in ranked2]
        assert scores1 == scores2

    def test_empty_ideas_returns_empty_list(self):
        engine = StrategyRankingEngine()
        ctx = _ctx()

        ranked = engine.rank([], ctx)
        assert ranked == []

    def test_get_scoring_breakdown(self):
        engine = StrategyRankingEngine()
        ctx = _ctx()
        idea = _idea(StrategyType.LONG_CALL)

        breakdown = engine.get_scoring_breakdown(idea, ctx)

        # Should have all component scores
        assert "direction_score" in breakdown
        assert "vol_score" in breakdown
        assert "elasticity_score" in breakdown
        assert "greek_score" in breakdown
        assert "move_score" in breakdown
        assert "capital_score" in breakdown
        assert "composite" in breakdown
        assert "final_score" in breakdown
        assert "weights" in breakdown

        # All scores should be 0-1
        for key in [
            "direction_score",
            "vol_score",
            "elasticity_score",
            "greek_score",
            "move_score",
            "capital_score",
            "composite",
            "final_score",
        ]:
            assert 0.0 <= breakdown[key] <= 1.0


# ============================================================================
# Test Regime-Specific Strategy Preferences
# ============================================================================


class TestRegimeSpecificPreferences:
    """Test that strategies align correctly with market regimes."""

    def test_high_energy_small_move_prefers_condors(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(
            direction=Direction.NEUTRAL,
            expected_move=ExpectedMove.SMALL,
            elastic_energy=2.5,  # High energy
        )

        ideas = [
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
            _idea(StrategyType.LONG_CALL),
        ]

        ranked = engine.rank(ideas, ctx)

        # Condor should win (neutral + small move + high energy)
        assert ranked[0].strategy_type == StrategyType.IRON_CONDOR

    def test_low_energy_large_move_prefers_outright(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(
            direction=Direction.BULLISH,
            expected_move=ExpectedMove.LARGE,
            elastic_energy=0.5,  # Low energy (easy to move)
        )

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.CALL_DEBIT_SPREAD),
            _idea(StrategyType.IRON_CONDOR),
        ]

        ranked = engine.rank(ideas, ctx)

        # Long call should win (bullish + large move + low energy)
        assert ranked[0].strategy_type == StrategyType.LONG_CALL

    def test_vol_crush_positive_gamma_prefers_income(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(
            direction=Direction.NEUTRAL,
            expected_move=ExpectedMove.SMALL,
            vol_regime=VolatilityRegime.VOL_CRUSH,
            gamma=2.0,  # Positive gamma (stable market)
        )

        ideas = [
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
            _idea(StrategyType.LONG_CALL),
        ]

        ranked = engine.rank(ideas, ctx)

        # Condor should win (vol crush + positive gamma + small move)
        assert ranked[0].strategy_type == StrategyType.IRON_CONDOR


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test boundary conditions and edge cases."""

    def test_all_scores_zero_liquidity(self):
        engine = StrategyRankingEngine()
        ctx = _ctx(liquidity=0.0)

        ideas = [_idea(StrategyType.LONG_CALL)]

        ranked = engine.rank(ideas, ctx)

        # With zero liquidity, final score should be zero
        assert ranked[0].ranking_score == 0.0

    def test_conflicting_signals_produces_valid_ranking(self):
        engine = StrategyRankingEngine()
        # Bullish but vol crush (conflicting for long call)
        ctx = _ctx(
            direction=Direction.BULLISH,
            vol_regime=VolatilityRegime.VOL_CRUSH,
        )

        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.CALL_DEBIT_SPREAD),
        ]

        ranked = engine.rank(ideas, ctx)

        # Should still produce valid ranking (spread may win due to vol crush)
        assert all(0.0 <= idea.ranking_score <= 1.0 for idea in ranked)

    def test_single_idea_still_gets_scored(self):
        engine = StrategyRankingEngine()
        ctx = _ctx()

        ideas = [_idea(StrategyType.LONG_CALL)]

        ranked = engine.rank(ideas, ctx)

        # Single idea should get valid score
        assert len(ranked) == 1
        assert 0.0 <= ranked[0].ranking_score <= 1.0
