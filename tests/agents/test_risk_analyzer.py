# tests/agents/test_risk_analyzer.py

"""
Tests for comprehensive risk analysis:
- PnL cone calculation
- Breakeven points
- Max profit/loss computation
- Capital efficiency metrics
"""

import pytest

from agents.trade_agent.options_strategies import (
    build_call_debit_spread,
    build_iron_condor,
    build_long_call,
    build_straddle,
)
from agents.trade_agent.risk_analyzer import (
    analyze_trade_risk,
    enhance_idea_with_risk_metrics,
)
from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    Timeframe,
    VolatilityRegime,
)


@pytest.fixture
def bullish_context():
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.BULLISH,
        confidence=0.7,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=1.0,
        gamma_exposure=0.0,
        vanna_exposure=0.0,
        charm_exposure=0.0,
        liquidity_score=0.8,
    )


@pytest.fixture
def neutral_context():
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.NEUTRAL,
        confidence=0.6,
        expected_move=ExpectedMove.SMALL,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=0.8,
        gamma_exposure=0.0,
        vanna_exposure=0.0,
        charm_exposure=0.0,
        liquidity_score=0.9,
    )


class TestPnLConeCalculation:
    def test_pnl_cone_has_correct_number_of_points(self, bullish_context):
        """PnL cone should have requested number of points."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(
            idea=idea,
            underlying_price=450.0,
            num_points=50,
        )
        
        assert len(metrics.pnl_cone) == 50

    def test_pnl_cone_covers_price_range(self, bullish_context):
        """PnL cone should span the specified price range."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(
            idea=idea,
            underlying_price=450.0,
            price_range_pct=0.20,  # ±20%
        )
        
        prices = [pt.underlying_price for pt in metrics.pnl_cone]
        
        # Should go from ~360 to ~540 (±20% of 450)
        assert min(prices) < 450 * 0.85
        assert max(prices) > 450 * 1.15

    def test_pnl_cone_monotonic_for_long_call(self, bullish_context):
        """Long call PnL should increase with underlying price."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # At high prices, PnL should be higher than at low prices
        low_price_pnl = metrics.pnl_cone[0].profit_loss
        high_price_pnl = metrics.pnl_cone[-1].profit_loss
        
        assert high_price_pnl > low_price_pnl


class TestBreakevenCalculation:
    def test_long_call_has_one_breakeven(self, bullish_context):
        """Long call should have one breakeven above strike."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Should have at least one breakeven
        assert len(metrics.breakeven_points) >= 1
        
        # Breakeven should be above strike
        strike = idea.legs[0].strike
        assert any(be > strike for be in metrics.breakeven_points)

    def test_iron_condor_has_two_breakevens(self, neutral_context):
        """Iron condor should have breakevens on both sides."""
        idea = build_iron_condor(neutral_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Should have breakevens on both wings
        # At least 2 breakeven points
        assert len(metrics.breakeven_points) >= 2

    def test_straddle_has_two_breakevens(self, neutral_context):
        """Straddle should have upper and lower breakevens."""
        idea = build_straddle(neutral_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Straddle has breakevens above and below ATM strike
        assert len(metrics.breakeven_points) >= 2
        
        # One below ATM, one above
        atm = 450.0
        assert any(be < atm for be in metrics.breakeven_points)
        assert any(be > atm for be in metrics.breakeven_points)


class TestMaxProfitLoss:
    def test_long_call_unlimited_profit(self, bullish_context):
        """Long call max profit should be high (approaching unlimited)."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Max profit should be substantial
        assert metrics.max_profit > 1000  # At least $1000 in the PnL cone

    def test_long_call_limited_loss(self, bullish_context):
        """Long call max loss should be limited to premium paid."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Max loss should be negative and finite
        assert metrics.max_loss < 0
        assert abs(metrics.max_loss) < 10000  # Reasonable premium

    def test_vertical_spread_defined_risk(self, bullish_context):
        """Vertical spread should have defined max profit and loss."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Both max profit and loss should be defined
        assert metrics.max_profit > 0
        assert metrics.max_loss < 0
        
        # Max profit should be limited (not infinite)
        assert metrics.max_profit < 10000

    def test_iron_condor_limited_profit_and_loss(self, neutral_context):
        """Iron condor has capped profit and loss."""
        idea = build_iron_condor(neutral_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Max profit from credit received
        assert metrics.max_profit > 0
        assert metrics.max_profit < 2000  # Limited credit
        
        # Max loss from wing width minus credit
        assert metrics.max_loss < 0
        assert abs(metrics.max_loss) < 5000


class TestRiskRewardRatio:
    def test_risk_reward_positive(self, bullish_context):
        """Risk/reward ratio should be positive."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        assert metrics.risk_reward_ratio > 0

    def test_iron_condor_favorable_risk_reward(self, neutral_context):
        """Iron condor should have decent risk/reward."""
        idea = build_iron_condor(neutral_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Typical IC: risk more to make less, but high probability
        # R:R often around 0.25 to 0.5
        assert 0.1 < metrics.risk_reward_ratio < 1.0


class TestCapitalEfficiency:
    def test_capital_required_calculation(self, bullish_context):
        """Capital required should be sum of debits."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Debit spread requires capital upfront
        assert metrics.capital_required > 0
        assert metrics.capital_required < 10000  # Reasonable for spread

    def test_return_on_risk_calculation(self, bullish_context):
        """Return on risk should be max_profit / capital_required."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # RoR should be positive and reasonable
        assert metrics.return_on_risk > 0
        
        # For spreads, typically 0.5 to 2.0
        assert 0.1 < metrics.return_on_risk < 10.0


class TestEnhanceIdea:
    def test_enhance_idea_adds_metrics(self, bullish_context):
        """Enhancing idea should populate all risk fields."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        # Before enhancement
        assert idea.max_profit is None
        assert idea.max_loss is None
        assert not idea.breakeven_prices
        
        # Enhance
        enhanced = enhance_idea_with_risk_metrics(
            idea=idea,
            underlying_price=450.0,
        )
        
        # After enhancement
        assert enhanced.max_profit is not None
        assert enhanced.max_loss is not None
        assert len(enhanced.breakeven_prices) > 0

    def test_enhance_idea_preserves_original_fields(self, bullish_context):
        """Enhancement should not overwrite existing fields."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        original_asset = idea.asset
        original_strategy = idea.strategy_type
        original_description = idea.description
        
        enhanced = enhance_idea_with_risk_metrics(
            idea=idea,
            underlying_price=450.0,
        )
        
        assert enhanced.asset == original_asset
        assert enhanced.strategy_type == original_strategy
        assert enhanced.description == original_description


class TestGreeksEvolution:
    def test_greeks_change_across_price_range(self, bullish_context):
        """Greeks should vary across the PnL cone."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        # Delta should vary across price range
        deltas = [pt.delta for pt in metrics.pnl_cone]
        
        # Should not all be the same
        assert len(set(deltas)) > 1

    def test_greeks_present_in_pnl_points(self, bullish_context):
        """Each PnL point should have Greeks."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        metrics = analyze_trade_risk(idea=idea, underlying_price=450.0)
        
        for point in metrics.pnl_cone:
            assert hasattr(point, 'delta')
            assert hasattr(point, 'gamma')
            assert hasattr(point, 'theta')
            assert hasattr(point, 'vega')
