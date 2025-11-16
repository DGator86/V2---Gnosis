# tests/agents/test_sizing_engine.py

from __future__ import annotations

from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    StrategyType,
    Timeframe,
    TradeIdea,
    VolatilityRegime,
)
from agents.trade_agent.sizing_engine import SizingConfig, SizingEngine


def _ctx(conf: float = 0.7) -> ComposerTradeContext:
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.BULLISH,
        confidence=conf,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=1.0,
        gamma_exposure=-1.0,
        vanna_exposure=0.3,
        charm_exposure=-0.2,
        liquidity_score=0.9,
    )


def _idea(strategy: StrategyType) -> TradeIdea:
    return TradeIdea(
        asset="SPY",
        strategy_type=strategy,
        description="test",
        legs=[],
        confidence=0.7,
    )


class TestSizingEngineBasics:
    """Test core sizing engine functionality."""

    def test_sizing_engine_allocates_nonzero_risk_for_positive_edge(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.7)
        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
        ]

        out = engine.size_ideas(ideas, ctx)

        assert len(out) == 2
        assert all(i.max_risk is not None for i in out)
        assert sum(i.max_risk or 0.0 for i in out) <= cfg.max_capital * cfg.max_portfolio_risk

    def test_sizing_engine_respects_max_risk_per_trade(self):
        cfg = SizingConfig(max_capital=100_000, max_risk_per_trade=0.005)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.8)
        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.LONG_PUT),
            _idea(StrategyType.STRADDLE),
        ]

        out = engine.size_ideas(ideas, ctx)

        for i in out:
            assert (i.max_risk or 0.0) <= cfg.max_capital * cfg.max_risk_per_trade

    def test_sizing_engine_zeroes_ideas_when_portfolio_at_max_risk(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.8)
        ideas = [_idea(StrategyType.LONG_CALL)]

        out = engine.size_ideas(ideas, ctx, existing_portfolio_risk=cfg.max_portfolio_risk)

        assert out[0].max_risk == 0.0
        assert out[0].recommended_size == 0
        assert out[0].ranking_score == 0.0


class TestKellyFormula:
    """Test Kelly-based sizing calculations."""

    def test_higher_confidence_increases_allocation(self):
        # Test with quarter-Kelly to keep fractions well below cap
        # Low conf (0.45): Kelly_raw=0.1028, quarter=0.0257
        # High conf (0.65): Kelly_raw=0.2306, quarter=0.0576
        # Both well below 0.10 cap, so differences are visible
        cfg = SizingConfig(
            max_capital=100_000,
            kelly_scale=0.25,  # Quarter Kelly
            max_risk_per_trade=0.10,
            max_portfolio_risk=0.20,
        )
        engine = SizingEngine(cfg)

        ctx_low = _ctx(conf=0.45)  # Minimum confidence
        ctx_high = _ctx(conf=0.65)  # Mid-high confidence

        ideas_low = [_idea(StrategyType.LONG_CALL)]
        ideas_high = [_idea(StrategyType.LONG_CALL)]

        out_low = engine.size_ideas(ideas_low, ctx_low)
        out_high = engine.size_ideas(ideas_high, ctx_high)

        assert (out_high[0].max_risk or 0.0) > (out_low[0].max_risk or 0.0)

    def test_high_elastic_energy_reduces_allocation(self):
        # Use low confidence so base Kelly is small, energy adjustment visible
        # Normal energy: Kelly ≈ 0.03
        # High energy (2.5): Kelly × 0.5 → ~0.015
        cfg = SizingConfig(
            max_capital=100_000,
            max_risk_per_trade=0.10,
            max_portfolio_risk=0.20,
        )
        engine = SizingEngine(cfg)

        ctx_normal = _ctx(conf=0.45)  # Low base confidence
        ctx_normal.elastic_energy = 1.0

        ctx_high = _ctx(conf=0.45)
        ctx_high.elastic_energy = 2.5

        ideas_normal = [_idea(StrategyType.LONG_CALL)]
        ideas_high = [_idea(StrategyType.LONG_CALL)]

        out_normal = engine.size_ideas(ideas_normal, ctx_normal)
        out_high = engine.size_ideas(ideas_high, ctx_high)

        # High energy should reduce allocation
        assert (out_high[0].max_risk or 0.0) < (out_normal[0].max_risk or 0.0)

    def test_low_elastic_energy_increases_allocation(self):
        # Use quarter-Kelly and low confidence to keep below cap
        # Normal (1.0): quarter_kelly * 1.0 = 0.0257
        # Low (0.5): quarter_kelly * 1.2 = 0.0308
        cfg = SizingConfig(
            max_capital=100_000,
            kelly_scale=0.25,  # Quarter Kelly
            max_risk_per_trade=0.10,
            max_portfolio_risk=0.20,
        )
        engine = SizingEngine(cfg)

        ctx_normal = _ctx(conf=0.45)
        ctx_normal.elastic_energy = 1.0

        ctx_low = _ctx(conf=0.45)
        ctx_low.elastic_energy = 0.5  # Triggers 1.2x boost

        ideas_normal = [_idea(StrategyType.LONG_CALL)]
        ideas_low = [_idea(StrategyType.LONG_CALL)]

        out_normal = engine.size_ideas(ideas_normal, ctx_normal)
        out_low = engine.size_ideas(ideas_low, ctx_low)

        # Low energy should increase allocation
        assert (out_low[0].max_risk or 0.0) > (out_normal[0].max_risk or 0.0)


class TestRMultipleCalculation:
    """Test expected R multiple calculations."""

    def test_convex_strategies_get_higher_r_multiple(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.7)

        idea_call = _idea(StrategyType.LONG_CALL)
        idea_condor = _idea(StrategyType.IRON_CONDOR)

        r_call = engine._expected_R_for_idea(idea_call, ctx)
        r_condor = engine._expected_R_for_idea(idea_condor, ctx)

        # Long call (convex) should have higher R than iron condor (income)
        assert r_call > r_condor

    def test_explosive_move_increases_r_multiple(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx_small = _ctx(conf=0.7)
        ctx_small.expected_move = ExpectedMove.SMALL

        ctx_explosive = _ctx(conf=0.7)
        ctx_explosive.expected_move = ExpectedMove.EXPLOSIVE

        idea = _idea(StrategyType.LONG_CALL)

        r_small = engine._expected_R_for_idea(idea, ctx_small)
        r_explosive = engine._expected_R_for_idea(idea, ctx_explosive)

        assert r_explosive > r_small


class TestConfigurableParameters:
    """Test that config parameters work as expected."""

    def test_kelly_scale_reduces_allocation(self):
        # Test that kelly_scale actually scales the allocation
        # Use low confidence so raw Kelly is small
        # Quarter (0.25): 0.1028 * 0.25 = 0.0257
        # Half (0.50): 0.1028 * 0.50 = 0.0514
        cfg_quarter = SizingConfig(
            max_capital=100_000,
            kelly_scale=0.25,
            max_risk_per_trade=0.10,
            max_portfolio_risk=0.20,
        )
        cfg_half = SizingConfig(
            max_capital=100_000,
            kelly_scale=0.5,
            max_risk_per_trade=0.10,
            max_portfolio_risk=0.20,
        )

        engine_quarter = SizingEngine(cfg_quarter)
        engine_half = SizingEngine(cfg_half)

        ctx = _ctx(conf=0.45)  # Low confidence
        ideas_quarter = [_idea(StrategyType.LONG_CALL)]
        ideas_half = [_idea(StrategyType.LONG_CALL)]

        out_quarter = engine_quarter.size_ideas(ideas_quarter, ctx)
        out_half = engine_half.size_ideas(ideas_half, ctx)

        # Half Kelly should allocate more than quarter Kelly
        assert (out_half[0].max_risk or 0.0) > (out_quarter[0].max_risk or 0.0)

    def test_max_portfolio_risk_limits_total_allocation(self):
        cfg = SizingConfig(
            max_capital=10_000,
            max_risk_per_trade=0.05,  # Allow 5% per trade
            max_portfolio_risk=0.08,  # But only 8% total
        )
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.8)
        # Create 3 ideas that would each want 5%
        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.LONG_PUT),
            _idea(StrategyType.STRADDLE),
        ]

        out = engine.size_ideas(ideas, ctx)

        total_risk = sum(i.max_risk or 0.0 for i in out)
        # Total should be capped at max_portfolio_risk
        assert total_risk <= cfg.max_capital * cfg.max_portfolio_risk


class TestRankingScore:
    """Test ranking score calculation."""

    def test_ranking_score_populated_for_all_ideas(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.7)
        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
        ]

        out = engine.size_ideas(ideas, ctx)

        for idea in out:
            assert idea.ranking_score is not None
            assert idea.ranking_score >= 0.0

    def test_ideas_sorted_by_ranking_score(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.7)
        ideas = [
            _idea(StrategyType.LONG_CALL),
            _idea(StrategyType.IRON_CONDOR),
            _idea(StrategyType.STRADDLE),
        ]

        out = engine.size_ideas(ideas, ctx)

        scores = [i.ranking_score or 0.0 for i in out]
        assert scores == sorted(scores, reverse=True)


class TestMaxProfitCalculation:
    """Test max profit is set based on R multiple."""

    def test_max_profit_reflects_r_multiple(self):
        cfg = SizingConfig(max_capital=10_000)
        engine = SizingEngine(cfg)

        ctx = _ctx(conf=0.7)
        idea = _idea(StrategyType.LONG_CALL)

        out = engine.size_ideas([idea], ctx)

        # Max profit should be max_risk * R
        r = engine._expected_R_for_idea(idea, ctx)
        expected_profit = (out[0].max_risk or 0.0) * r

        assert out[0].max_profit is not None
        assert abs((out[0].max_profit or 0.0) - expected_profit) < 0.01
