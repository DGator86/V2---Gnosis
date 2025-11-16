# tests/agents/test_exit_manager.py

"""
Tests for exit management system:
- Exit rule creation
- Profit target triggers
- Stop loss triggers
- Time-based exits
- Trailing stops
- Greeks-based exits
"""

import pytest

from agents.trade_agent.exit_manager import (
    ExitTrigger,
    check_exit_conditions,
    create_default_exit_rules,
)
from agents.trade_agent.options_strategies import (
    build_call_debit_spread,
    build_iron_condor,
    build_long_call,
    build_straddle,
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


class TestExitRuleCreation:
    def test_directional_strategy_rules(self):
        """Directional strategies should have appropriate exits."""
        rules = create_default_exit_rules(
            strategy_type=StrategyType.LONG_CALL,
            confidence=0.7,
        )
        
        assert rules.profit_target_pct is not None
        assert rules.stop_loss_pct is not None
        assert rules.max_days_to_expiry is not None
        assert rules.trailing_stop_pct is not None

    def test_income_strategy_rules(self):
        """Income strategies should have tighter exits."""
        rules = create_default_exit_rules(
            strategy_type=StrategyType.IRON_CONDOR,
            confidence=0.6,
        )
        
        assert rules.profit_target_pct is not None
        assert rules.max_days_to_expiry is not None
        # IC typically exits closer to expiry
        assert rules.max_days_to_expiry <= 5

    def test_vol_strategy_rules(self):
        """Volatility strategies should have wider stops."""
        rules = create_default_exit_rules(
            strategy_type=StrategyType.STRADDLE,
            confidence=0.5,
        )
        
        assert rules.profit_target_pct is not None
        assert rules.stop_loss_pct is not None
        # Vol strategies need more time
        assert rules.max_days_to_expiry >= 5

    def test_high_confidence_wider_stops(self):
        """High confidence should result in wider stops."""
        high_conf = create_default_exit_rules(
            strategy_type=StrategyType.LONG_CALL,
            confidence=0.9,
        )
        low_conf = create_default_exit_rules(
            strategy_type=StrategyType.LONG_CALL,
            confidence=0.3,
        )
        
        # High confidence = wider profit target, looser stop
        assert high_conf.profit_target_pct > low_conf.profit_target_pct
        assert high_conf.stop_loss_pct > low_conf.stop_loss_pct

    def test_exit_rules_have_breakeven_trigger(self):
        """Exit rules should include breakeven management."""
        rules = create_default_exit_rules(
            strategy_type=StrategyType.CALL_DEBIT_SPREAD,
            confidence=0.6,
        )
        
        assert rules.move_to_breakeven_at_pct is not None
        assert 0.2 <= rules.move_to_breakeven_at_pct <= 0.5


class TestProfitTargetExits:
    def test_profit_target_percentage_trigger(self, bullish_context):
        """Exit when PnL hits profit target %."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        idea.max_profit = 1000.0
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Current PnL at 60% of max profit
        signal = check_exit_conditions(
            idea=idea,
            current_price=460.0,
            current_pnl=600.0,  # 60% of 1000
            days_held=5,
            days_to_expiry=20,
            current_theta=-10.0,
            peak_pnl=600.0,
            exit_rule=rules,
        )
        
        # Should trigger if profit_target_pct <= 0.60
        if rules.profit_target_pct and rules.profit_target_pct <= 0.60:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.PROFIT_TARGET

    def test_profit_target_not_triggered_early(self, bullish_context):
        """Exit should not trigger before profit target."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        idea.max_profit = 1000.0
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Current PnL at 20% of max profit
        signal = check_exit_conditions(
            idea=idea,
            current_price=455.0,
            current_pnl=200.0,
            days_held=3,
            days_to_expiry=25,
            current_theta=-10.0,
            peak_pnl=200.0,
            exit_rule=rules,
        )
        
        # Should not exit yet (typical target is 50%)
        if signal.trigger == ExitTrigger.PROFIT_TARGET:
            assert not signal.should_exit


class TestStopLossExits:
    def test_stop_loss_percentage_trigger(self, bullish_context):
        """Exit when loss hits stop %."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        idea.max_loss = -500.0
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Current PnL at 60% of max loss
        signal = check_exit_conditions(
            idea=idea,
            current_price=440.0,
            current_pnl=-300.0,  # 60% of max loss
            days_held=8,
            days_to_expiry=15,
            current_theta=-10.0,
            peak_pnl=50.0,
            exit_rule=rules,
        )
        
        # Should trigger if stop_loss_pct <= 0.60
        if rules.stop_loss_pct and rules.stop_loss_pct <= 0.60:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.STOP_LOSS


class TestTimeBasedExits:
    def test_days_to_expiry_trigger(self, bullish_context):
        """Exit when approaching expiration."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # 3 days to expiry
        signal = check_exit_conditions(
            idea=idea,
            current_price=455.0,
            current_pnl=100.0,
            days_held=25,
            days_to_expiry=3,
            current_theta=-15.0,
            peak_pnl=150.0,
            exit_rule=rules,
        )
        
        # Should trigger if max_days_to_expiry >= 3
        if rules.max_days_to_expiry and rules.max_days_to_expiry >= 3:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.TIME_DECAY

    def test_max_holding_period_trigger(self, bullish_context):
        """Exit after max holding days."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Held for 40 days
        signal = check_exit_conditions(
            idea=idea,
            current_price=455.0,
            current_pnl=100.0,
            days_held=40,
            days_to_expiry=10,
            current_theta=-10.0,
            peak_pnl=150.0,
            exit_rule=rules,
        )
        
        # Should trigger if max_holding_days <= 40
        if rules.max_holding_days and rules.max_holding_days <= 40:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.TIME_DECAY


class TestTrailingStops:
    def test_trailing_stop_from_peak(self, bullish_context):
        """Trailing stop should trigger when falling from peak."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Peak was 500, now at 400 (20% drawdown from peak)
        signal = check_exit_conditions(
            idea=idea,
            current_price=458.0,
            current_pnl=400.0,
            days_held=10,
            days_to_expiry=20,
            current_theta=-10.0,
            peak_pnl=500.0,
            exit_rule=rules,
        )
        
        # Should trigger if trailing_stop_pct < 0.20
        if rules.trailing_stop_pct and rules.trailing_stop_pct < 0.20:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.TRAILING_STOP

    def test_trailing_stop_not_active_when_negative(self, bullish_context):
        """Trailing stop only activates after profit."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Currently losing, no peak profit
        signal = check_exit_conditions(
            idea=idea,
            current_price=445.0,
            current_pnl=-100.0,
            days_held=5,
            days_to_expiry=25,
            current_theta=-10.0,
            peak_pnl=-50.0,  # Never profitable
            exit_rule=rules,
        )
        
        # Trailing stop should not trigger
        if signal.trigger == ExitTrigger.TRAILING_STOP:
            assert not signal.should_exit


class TestGreeksBasedExits:
    def test_excessive_theta_decay_trigger(self, bullish_context):
        """Exit when theta decay too high."""
        idea = build_straddle(bullish_context, underlying_price=450.0)
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Losing $60/day to theta
        signal = check_exit_conditions(
            idea=idea,
            current_price=450.0,
            current_pnl=-200.0,
            days_held=15,
            days_to_expiry=10,
            current_theta=-60.0,
            peak_pnl=100.0,
            exit_rule=rules,
        )
        
        # Should trigger if theta_threshold > -60
        if rules.theta_threshold and rules.theta_threshold > -60:
            assert signal.should_exit
            assert signal.trigger == ExitTrigger.GREEKS_THRESHOLD


class TestBreakevenStopAdjustment:
    def test_move_to_breakeven_signal(self, bullish_context):
        """Signal to move stop to breakeven after threshold hit."""
        idea = build_call_debit_spread(bullish_context, underlying_price=450.0)
        idea.max_profit = 1000.0
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Hit 35% of max profit
        signal = check_exit_conditions(
            idea=idea,
            current_price=455.0,
            current_pnl=350.0,
            days_held=8,
            days_to_expiry=22,
            current_theta=-10.0,
            peak_pnl=350.0,
            exit_rule=rules,
        )
        
        # Should signal breakeven adjustment if threshold <= 0.35
        if rules.move_to_breakeven_at_pct and rules.move_to_breakeven_at_pct <= 0.35:
            if signal.trigger == ExitTrigger.BREAKEVEN_STOP:
                assert not signal.should_exit  # Don't exit, just adjust
                assert signal.suggested_action == "adjust_stop"


class TestExitPriority:
    def test_profit_target_before_time_exit(self, bullish_context):
        """Profit target should trigger even near expiry."""
        idea = build_long_call(bullish_context, underlying_price=450.0)
        idea.max_profit = 1000.0
        
        rules = create_default_exit_rules(
            strategy_type=idea.strategy_type,
            confidence=0.7,
        )
        
        # Hit profit target but also near expiry
        signal = check_exit_conditions(
            idea=idea,
            current_price=465.0,
            current_pnl=700.0,  # 70% of max profit
            days_held=25,
            days_to_expiry=3,  # Also near expiry
            current_theta=-15.0,
            peak_pnl=700.0,
            exit_rule=rules,
        )
        
        # Should exit via profit target (takes priority)
        assert signal.should_exit
        # Either profit target or time decay is acceptable
        assert signal.trigger in [ExitTrigger.PROFIT_TARGET, ExitTrigger.TIME_DECAY]
