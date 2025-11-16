# tests/agents/test_new_strategies.py

"""
Tests for new strategy builders:
- Calendar spreads
- Diagonal spreads
- Broken wing butterflies
- Synthetic long/short
- Reverse iron condor
"""

import pytest

from agents.trade_agent.options_strategies import (
    build_broken_wing_butterfly,
    build_calendar_spread,
    build_diagonal_spread,
    build_reverse_iron_condor,
    build_synthetic_long,
    build_synthetic_short,
)
from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    StrategyType,
    Timeframe,
    VolatilityRegime,
)


@pytest.fixture
def bullish_context():
    """Bullish market context."""
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
def bearish_context():
    """Bearish market context."""
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.BEARISH,
        confidence=0.6,
        expected_move=ExpectedMove.SMALL,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=1.2,
        gamma_exposure=0.0,
        vanna_exposure=0.0,
        charm_exposure=0.0,
        liquidity_score=0.7,
    )


@pytest.fixture
def vol_expansion_context():
    """Expecting volatility expansion."""
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.NEUTRAL,
        confidence=0.5,
        expected_move=ExpectedMove.LARGE,
        volatility_regime=VolatilityRegime.VOL_EXPANSION,
        timeframe=Timeframe.SWING,
        elastic_energy=2.0,
        gamma_exposure=0.5,
        vanna_exposure=0.3,
        charm_exposure=0.1,
        liquidity_score=0.6,
    )


class TestCalendarSpread:
    def test_calendar_spread_structure(self, bullish_context):
        """Calendar spread has 2 legs: short near, long far."""
        idea = build_calendar_spread(bullish_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.CALENDAR_SPREAD
        assert len(idea.legs) == 2
        
        # First leg: short near-term
        assert idea.legs[0].side == "short"
        assert idea.legs[0].option_type == "call"
        
        # Second leg: long far-term
        assert idea.legs[1].side == "long"
        assert idea.legs[1].option_type == "call"
        
        # Same strike
        assert idea.legs[0].strike == idea.legs[1].strike
        
        # Different expiries
        assert idea.legs[0].expiry != idea.legs[1].expiry

    def test_calendar_spread_greeks(self, bullish_context):
        """Calendar spread should have positive theta, low delta."""
        idea = build_calendar_spread(bullish_context, underlying_price=450.0)
        
        assert idea.greeks_profile is not None
        assert abs(idea.greeks_profile.delta) < 0.2  # Near neutral
        assert idea.greeks_profile.theta > 0  # Positive theta
        assert idea.greeks_profile.vega > 0  # Benefits from vol increase


class TestDiagonalSpread:
    def test_diagonal_spread_structure(self, bullish_context):
        """Diagonal spread has different strikes and expiries."""
        idea = build_diagonal_spread(bullish_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.DIAGONAL_SPREAD
        assert len(idea.legs) == 2
        
        # Long far-term, short near-term
        long_leg = [leg for leg in idea.legs if leg.side == "long"][0]
        short_leg = [leg for leg in idea.legs if leg.side == "short"][0]
        
        # Different strikes
        assert long_leg.strike != short_leg.strike
        
        # Different expiries
        assert long_leg.expiry != short_leg.expiry

    def test_diagonal_spread_directional_bias(self, bullish_context):
        """Diagonal spread should have directional delta."""
        idea = build_diagonal_spread(bullish_context, underlying_price=450.0)
        
        assert idea.greeks_profile is not None
        assert idea.greeks_profile.delta > 0.15  # Moderate bullish
        assert idea.greeks_profile.theta > 0  # Positive theta


class TestBrokenWingButterfly:
    def test_broken_wing_structure(self, bullish_context):
        """Broken wing butterfly has 3 strikes, asymmetric wings."""
        idea = build_broken_wing_butterfly(bullish_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.BROKEN_WING_BUTTERFLY
        assert len(idea.legs) == 3
        
        # 1 long lower, 2 short middle, 1 long upper
        long_legs = [leg for leg in idea.legs if leg.side == "long"]
        short_legs = [leg for leg in idea.legs if leg.side == "short"]
        
        assert len(long_legs) == 2
        assert len(short_legs) == 1
        assert short_legs[0].quantity == 2

    def test_broken_wing_bullish_skew(self, bullish_context):
        """Bullish broken wing should have upper wing wider."""
        idea = build_broken_wing_butterfly(bullish_context, underlying_price=450.0)
        
        strikes = sorted([leg.strike for leg in idea.legs])
        
        # Upper wing wider than lower wing
        lower_width = strikes[1] - strikes[0]
        upper_width = strikes[2] - strikes[1]
        
        assert upper_width > lower_width

    def test_broken_wing_bearish_skew(self, bearish_context):
        """Bearish broken wing should have lower wing wider."""
        idea = build_broken_wing_butterfly(bearish_context, underlying_price=450.0)
        
        strikes = sorted([leg.strike for leg in idea.legs])
        
        # Lower wing wider than upper wing
        lower_width = strikes[1] - strikes[0]
        upper_width = strikes[2] - strikes[1]
        
        assert lower_width > upper_width


class TestSyntheticPositions:
    def test_synthetic_long_structure(self, bullish_context):
        """Synthetic long = long call + short put at same strike."""
        idea = build_synthetic_long(bullish_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.SYNTHETIC_LONG
        assert len(idea.legs) == 2
        
        call_leg = [leg for leg in idea.legs if leg.option_type == "call"][0]
        put_leg = [leg for leg in idea.legs if leg.option_type == "put"][0]
        
        # Long call, short put
        assert call_leg.side == "long"
        assert put_leg.side == "short"
        
        # Same strike (ATM)
        assert call_leg.strike == put_leg.strike
        assert call_leg.expiry == put_leg.expiry

    def test_synthetic_long_delta(self, bullish_context):
        """Synthetic long should have ~1.0 delta (like long stock)."""
        idea = build_synthetic_long(bullish_context, underlying_price=450.0)
        
        assert idea.greeks_profile is not None
        assert abs(idea.greeks_profile.delta - 1.0) < 0.1

    def test_synthetic_short_structure(self, bearish_context):
        """Synthetic short = long put + short call at same strike."""
        idea = build_synthetic_short(bearish_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.SYNTHETIC_SHORT
        assert len(idea.legs) == 2
        
        call_leg = [leg for leg in idea.legs if leg.option_type == "call"][0]
        put_leg = [leg for leg in idea.legs if leg.option_type == "put"][0]
        
        # Long put, short call
        assert put_leg.side == "long"
        assert call_leg.side == "short"
        
        # Same strike (ATM)
        assert call_leg.strike == put_leg.strike

    def test_synthetic_short_delta(self, bearish_context):
        """Synthetic short should have ~-1.0 delta (like short stock)."""
        idea = build_synthetic_short(bearish_context, underlying_price=450.0)
        
        assert idea.greeks_profile is not None
        assert abs(idea.greeks_profile.delta - (-1.0)) < 0.1


class TestReverseIronCondor:
    def test_reverse_iron_condor_structure(self, vol_expansion_context):
        """Reverse IC = long body, short wings."""
        idea = build_reverse_iron_condor(vol_expansion_context, underlying_price=450.0)
        
        assert idea.strategy_type == StrategyType.REVERSE_IRON_CONDOR
        assert len(idea.legs) == 4
        
        # 2 long (body), 2 short (wings)
        long_legs = [leg for leg in idea.legs if leg.side == "long"]
        short_legs = [leg for leg in idea.legs if leg.side == "short"]
        
        assert len(long_legs) == 2
        assert len(short_legs) == 2

    def test_reverse_iron_condor_greeks(self, vol_expansion_context):
        """Reverse IC should have positive gamma and vega."""
        idea = build_reverse_iron_condor(vol_expansion_context, underlying_price=450.0)
        
        assert idea.greeks_profile is not None
        assert abs(idea.greeks_profile.delta) < 0.1  # Market neutral
        assert idea.greeks_profile.gamma > 0  # Positive gamma
        assert idea.greeks_profile.vega > 0  # Benefits from vol increase
        assert idea.greeks_profile.theta < 0  # Negative theta (long premium)

    def test_reverse_iron_condor_wing_structure(self, vol_expansion_context):
        """Verify long body is inside short wings."""
        idea = build_reverse_iron_condor(vol_expansion_context, underlying_price=450.0)
        
        put_legs = [leg for leg in idea.legs if leg.option_type == "put"]
        call_legs = [leg for leg in idea.legs if leg.option_type == "call"]
        
        # Get strikes
        long_put = [leg for leg in put_legs if leg.side == "long"][0]
        short_put = [leg for leg in put_legs if leg.side == "short"][0]
        long_call = [leg for leg in call_legs if leg.side == "long"][0]
        short_call = [leg for leg in call_legs if leg.side == "short"][0]
        
        # Long body should be closer to ATM than short wings
        assert long_put.strike > short_put.strike
        assert long_call.strike < short_call.strike


class TestStrategyIntegration:
    """Integration tests for all strategies."""
    
    def test_all_strategies_return_valid_ideas(self, bullish_context):
        """All strategy builders should return valid TradeIdea objects."""
        
        underlying = 450.0
        
        strategies = [
            build_calendar_spread,
            build_diagonal_spread,
            build_broken_wing_butterfly,
            build_synthetic_long,
            build_reverse_iron_condor,
        ]
        
        for builder in strategies:
            idea = builder(bullish_context, underlying)
            
            # Basic validation
            assert idea.asset == "SPY"
            assert idea.strategy_type is not None
            assert len(idea.description) > 0
            assert len(idea.legs) >= 2
            assert idea.confidence == bullish_context.confidence
            assert idea.greeks_profile is not None

    def test_strategies_have_appropriate_greeks(self, bullish_context):
        """Verify Greeks make sense for each strategy family."""
        
        underlying = 450.0
        
        # Time decay strategies: positive theta
        calendar = build_calendar_spread(bullish_context, underlying)
        assert calendar.greeks_profile.theta > 0
        
        diagonal = build_diagonal_spread(bullish_context, underlying)
        assert diagonal.greeks_profile.theta > 0
        
        # Volatility strategies: negative theta, positive vega
        reverse_ic = build_reverse_iron_condor(bullish_context, underlying)
        assert reverse_ic.greeks_profile.theta < 0
        assert reverse_ic.greeks_profile.vega > 0
        
        # Synthetic: near-zero offsetting Greeks
        synthetic = build_synthetic_long(bullish_context, underlying)
        assert abs(synthetic.greeks_profile.gamma) < 0.1
        assert abs(synthetic.greeks_profile.theta) < 0.1
        assert abs(synthetic.greeks_profile.vega) < 0.1
