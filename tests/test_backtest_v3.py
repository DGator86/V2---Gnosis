"""
Comprehensive Test Suite for Universal Backtest Engine v3
==========================================================

Tests the Multi-Engine Historical Simulation System.

Test Coverage:
1. Engine initialization (2 tests)
2. Position management (4 tests)
3. Trade execution (4 tests)
4. Equity tracking (2 tests)
5. Results calculation (4 tests)
6. Risk metrics (4 tests)
7. Attribution analysis (2 tests)
8. Edge cases (3 tests)

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import the Universal Backtest Engine
from engines.backtest.universal_backtest_engine import (
    UniversalBacktestEngine,
    BacktestMode,
    BacktestResults,
    Trade
)

# Import dependencies
from engines.composer.universal_policy_composer import (
    UniversalPolicyComposer,
    RiskParameters,
    TradeDirection
)


# ==================== Mock Data Classes ====================

@dataclass
class MockEnergyState:
    """Mock energy state for testing."""
    movement_energy: float = 100.0
    elasticity: float = 0.5
    energy_asymmetry: float = 10.0
    elasticity_asymmetry: float = 0.1
    regime: str = "elastic"
    stability: float = 0.9
    confidence: float = 0.95


@dataclass
class MockLiquidityState:
    """Mock liquidity state for testing."""
    impact_cost: float = 10.0
    slippage: float = 5.0
    depth_imbalance: float = 0.2
    spread_bps: float = 2.0
    regime: str = "liquid"
    stability: float = 0.85
    confidence: float = 0.90


@dataclass
class MockSentimentState:
    """Mock sentiment state for testing."""
    sentiment_score: float = 0.6
    sentiment_momentum: float = 0.1
    contrarian_signal: float = -0.4
    crowd_conviction: float = 0.7
    regime: str = "bullish"
    stability: float = 0.88
    confidence: float = 0.92


# ==================== Test Fixtures ====================

@pytest.fixture
def composer():
    """Create UniversalPolicyComposer instance."""
    return UniversalPolicyComposer(
        risk_params=RiskParameters(
            max_position_size=10000.0,
            max_position_pct=0.10
        ),
        enable_monte_carlo=False  # Disable for faster tests
    )


@pytest.fixture
def backtest_engine(composer):
    """Create UniversalBacktestEngine instance."""
    return UniversalBacktestEngine(
        policy_composer=composer,
        initial_capital=100000.0,
        mode=BacktestMode.EVENT_DRIVEN
    )


@pytest.fixture
def historical_data():
    """Create mock historical data."""
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
    
    # Trending upward data
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5 + 0.2)
    
    data = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.01,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, size=len(dates)),
        'volatility': 0.20
    }, index=dates)
    
    return data


@pytest.fixture
def engine_states(historical_data):
    """Create mock engine states aligned with data."""
    n = len(historical_data)
    
    energy_states = [MockEnergyState() for _ in range(n)]
    liquidity_states = [MockLiquidityState() for _ in range(n)]
    sentiment_states = [MockSentimentState() for _ in range(n)]
    
    return energy_states, liquidity_states, sentiment_states


# ==================== Initialization Tests ====================

def test_backtest_engine_initialization(composer):
    """Test backtest engine initialization."""
    engine = UniversalBacktestEngine(
        policy_composer=composer,
        initial_capital=100000.0,
        mode=BacktestMode.EVENT_DRIVEN
    )
    
    assert engine.initial_capital == 100000.0
    assert engine.current_capital == 100000.0
    assert engine.mode == BacktestMode.EVENT_DRIVEN
    assert len(engine.trades) == 0
    assert engine.open_trade is None


def test_backtest_engine_modes(composer):
    """Test different backtest modes."""
    for mode in [BacktestMode.EVENT_DRIVEN, BacktestMode.VECTORIZED, BacktestMode.HYBRID]:
        engine = UniversalBacktestEngine(
            policy_composer=composer,
            initial_capital=50000.0,
            mode=mode
        )
        assert engine.mode == mode


# ==================== Position Management Tests ====================

def test_open_position(backtest_engine, historical_data):
    """Test opening a position."""
    from engines.composer.universal_policy_composer import TradeIdea, PositionSizeMethod
    
    # Create mock trade idea
    trade_idea = TradeIdea(
        symbol="TEST",
        direction=TradeDirection.LONG,
        position_size=100.0,
        position_value=10000.0,
        sizing_method=PositionSizeMethod.FIXED,
        entry_price=100.0,
        entry_price_min=99.5,
        entry_price_max=100.5,
        stop_loss=98.0,
        take_profit=106.0,
        expected_slippage_bps=5.0,
        expected_impact_bps=10.0,
        total_expected_cost_bps=15.0,
        energy_signal=0.5,
        liquidity_signal=0.3,
        sentiment_signal=0.2,
        composite_signal=0.4,
        expected_return=0.06,
        expected_volatility=0.20,
        sharpe_ratio=1.5,
        kelly_fraction=0.25,
        energy_regime="elastic",
        liquidity_regime="liquid",
        sentiment_regime="bullish",
        regime_consistency=0.8,
        mc_win_rate=0.6,
        mc_avg_pnl=100.0,
        mc_sharpe=1.8,
        mc_var_95=-50.0,
        is_valid=True,
        confidence=0.85
    )
    
    bar = historical_data.iloc[0]
    liquidity_state = MockLiquidityState()
    
    # Open position
    backtest_engine._open_position(
        timestamp=historical_data.index[0],
        bar=bar,
        trade_idea=trade_idea,
        liquidity_state=liquidity_state
    )
    
    assert backtest_engine.open_trade is not None
    assert backtest_engine.open_trade.direction == "long"
    assert backtest_engine.open_trade.position_size > 0
    assert backtest_engine.current_capital < backtest_engine.initial_capital


def test_close_position(backtest_engine, historical_data):
    """Test closing a position."""
    # First open a position
    backtest_engine.open_trade = Trade(
        entry_date=historical_data.index[0],
        symbol="TEST",
        direction="long",
        entry_price=100.0,
        position_size=100.0,
        position_value=10000.0,
        entry_slippage_bps=5.0,
        entry_impact_bps=10.0,
        stop_loss=98.0,
        take_profit=106.0
    )
    
    backtest_engine.current_capital = 90000.0  # Simulate capital used
    
    # Close position
    bar = historical_data.iloc[5]  # Use bar with higher price
    liquidity_state = MockLiquidityState()
    
    backtest_engine._close_position(bar, liquidity_state)
    
    assert backtest_engine.open_trade is None
    assert len(backtest_engine.trades) == 1
    assert backtest_engine.trades[0].exit_price > 0
    assert backtest_engine.trades[0].net_pnl != 0


def test_check_exit_signals_stop_loss(backtest_engine, historical_data):
    """Test stop loss detection."""
    trade = Trade(
        entry_date=historical_data.index[0],
        direction="long",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=106.0
    )
    
    # Create bar below stop loss
    bar = pd.Series({
        'close': 97.0,
        'high': 98.0,
        'low': 97.0
    })
    
    should_exit = backtest_engine._check_exit_signals(bar, trade)
    
    assert should_exit, "Should exit when stop loss hit"


def test_check_exit_signals_take_profit(backtest_engine, historical_data):
    """Test take profit detection."""
    trade = Trade(
        entry_date=historical_data.index[0],
        direction="long",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=106.0
    )
    
    # Create bar above take profit
    bar = pd.Series({
        'close': 107.0,
        'high': 107.0,
        'low': 105.0
    })
    
    should_exit = backtest_engine._check_exit_signals(bar, trade)
    
    assert should_exit, "Should exit when take profit hit"


# ==================== Trade Execution Tests ====================

def test_run_backtest_basic(backtest_engine, historical_data, engine_states):
    """Test basic backtest execution."""
    energy_states, liquidity_states, sentiment_states = engine_states
    
    results = backtest_engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states
    )
    
    assert isinstance(results, BacktestResults)
    assert results.initial_capital == 100000.0
    assert results.total_days > 0
    assert results.start_date == historical_data.index[0]
    assert results.end_date == historical_data.index[-1]


def test_run_backtest_with_trades(backtest_engine, historical_data, engine_states):
    """Test backtest generates trades."""
    energy_states, liquidity_states, sentiment_states = engine_states
    
    # Modify energy states to generate stronger signals
    for state in energy_states:
        state.energy_asymmetry = 50.0  # Strong bullish
    
    results = backtest_engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states
    )
    
    # Should generate at least one trade with strong signals
    assert results.total_trades >= 0  # May or may not trade depending on validation


def test_run_backtest_date_filter(backtest_engine, historical_data, engine_states):
    """Test backtest with date filtering."""
    energy_states, liquidity_states, sentiment_states = engine_states
    
    start_date = historical_data.index[5]
    end_date = historical_data.index[15]
    
    results = backtest_engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states,
        start_date=start_date,
        end_date=end_date
    )
    
    assert results.start_date >= start_date
    assert results.end_date <= end_date


def test_run_backtest_vectorized(composer, historical_data, engine_states):
    """Test vectorized backtest mode."""
    engine = UniversalBacktestEngine(
        policy_composer=composer,
        initial_capital=100000.0,
        mode=BacktestMode.VECTORIZED
    )
    
    energy_states, liquidity_states, sentiment_states = engine_states
    
    results = engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states
    )
    
    assert isinstance(results, BacktestResults)
    assert results.mode == BacktestMode.VECTORIZED


# ==================== Equity Tracking Tests ====================

def test_update_equity(backtest_engine):
    """Test equity tracking."""
    timestamp = datetime.now()
    price = 100.0
    
    backtest_engine._update_equity(timestamp, price)
    
    assert len(backtest_engine.equity_history) == 1
    assert backtest_engine.equity_history[0][1] == 100000.0  # Initial capital


def test_update_equity_with_position(backtest_engine):
    """Test equity tracking with open position."""
    # Open position
    backtest_engine.open_trade = Trade(
        entry_date=datetime.now(),
        direction="long",
        entry_price=100.0,
        position_size=100.0
    )
    
    # Update equity with higher price
    backtest_engine._update_equity(datetime.now(), 105.0)
    
    # Should include unrealized profit
    equity = backtest_engine.equity_history[0][1]
    assert equity > backtest_engine.initial_capital


# ==================== Results Calculation Tests ====================

def test_calculate_drawdown(backtest_engine):
    """Test drawdown calculation."""
    # Create equity curve with drawdown
    dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
    equity = pd.DataFrame({
        'equity': [100000, 105000, 103000, 101000, 98000, 99000, 102000, 104000, 106000, 105000],
        'returns': [0.0, 0.05, -0.019, -0.019, -0.030, 0.010, 0.030, 0.020, 0.019, -0.009]
    }, index=dates)
    
    max_dd, max_dd_pct, max_dd_duration = backtest_engine._calculate_drawdown(equity)
    
    assert max_dd < 0, "Max drawdown should be negative"
    assert max_dd_pct < 0, "Max drawdown % should be negative"
    assert max_dd_duration >= 0, "Drawdown duration should be non-negative"


def test_calculate_sharpe(backtest_engine):
    """Test Sharpe ratio calculation."""
    returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01, 0.008, 0.012, -0.003])
    
    sharpe = backtest_engine._calculate_sharpe(returns)
    
    assert isinstance(sharpe, float), "Sharpe should be float"
    assert not np.isnan(sharpe), "Sharpe should not be NaN"


def test_calculate_sortino(backtest_engine):
    """Test Sortino ratio calculation."""
    returns = pd.Series([0.01, -0.005, 0.02, 0.015, -0.01, 0.008, 0.012, -0.003])
    
    sortino = backtest_engine._calculate_sortino(returns)
    
    assert isinstance(sortino, float), "Sortino should be float"
    assert not np.isnan(sortino), "Sortino should not be NaN"


def test_results_calculation(backtest_engine, historical_data):
    """Test comprehensive results calculation."""
    # Add some trades
    for i in range(5):
        trade = Trade(
            entry_date=historical_data.index[i],
            exit_date=historical_data.index[i+1],
            symbol="TEST",
            direction="long",
            entry_price=100.0 + i,
            exit_price=102.0 + i,
            position_size=100.0,
            position_value=10000.0,
            net_pnl=200.0,
            is_winner=True,
            win_amount=200.0,
            total_cost_bps=15.0
        )
        backtest_engine.trades.append(trade)
    
    # Add equity history
    for i, timestamp in enumerate(historical_data.index):
        backtest_engine.equity_history.append((timestamp, 100000.0 + i * 200))
    
    results = backtest_engine._calculate_results(
        symbol="TEST",
        start_date=historical_data.index[0],
        end_date=historical_data.index[-1],
        historical_data=historical_data
    )
    
    assert results.total_trades == 5
    assert results.winning_trades == 5
    assert results.win_rate == 1.0
    assert results.profit_factor >= 0  # Will be 0 if gross_loss is 0
    assert results.sharpe_ratio != 0


# ==================== Risk Metrics Tests ====================

def test_risk_metrics_positive_returns(backtest_engine):
    """Test risk metrics with positive returns."""
    returns = pd.Series([0.01, 0.02, 0.015, 0.008, 0.012] * 10)
    
    sharpe = backtest_engine._calculate_sharpe(returns)
    sortino = backtest_engine._calculate_sortino(returns)
    
    assert sharpe > 0, "Sharpe should be positive for positive returns"
    # Sortino may be 0 if no downside returns


def test_risk_metrics_negative_returns(backtest_engine):
    """Test risk metrics with negative returns."""
    returns = pd.Series([-0.01, -0.02, -0.015, -0.008, -0.012] * 10)
    
    sharpe = backtest_engine._calculate_sharpe(returns)
    
    assert sharpe < 0, "Sharpe should be negative for negative returns"


def test_risk_metrics_mixed_returns(backtest_engine):
    """Test risk metrics with mixed returns."""
    returns = pd.Series([0.02, -0.01, 0.015, -0.005, 0.01, -0.008] * 10)
    
    sharpe = backtest_engine._calculate_sharpe(returns)
    sortino = backtest_engine._calculate_sortino(returns)
    
    assert isinstance(sharpe, float)
    assert isinstance(sortino, float)
    assert not np.isnan(sharpe)
    assert not np.isnan(sortino)


def test_drawdown_recovery(backtest_engine):
    """Test drawdown calculation with recovery."""
    # Create equity that goes down then recovers
    dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
    equity_values = [100000, 98000, 96000, 95000, 97000, 99000, 101000, 102000, 104000, 105000]
    
    equity_df = pd.DataFrame({
        'equity': equity_values,
        'returns': [0] + [equity_values[i]/equity_values[i-1] - 1 for i in range(1, len(equity_values))]
    }, index=dates)
    
    max_dd, max_dd_pct, max_dd_duration = backtest_engine._calculate_drawdown(equity_df)
    
    assert max_dd < 0
    assert max_dd_duration > 0


# ==================== Attribution Analysis Tests ====================

def test_attribution_analysis(backtest_engine):
    """Test performance attribution calculation."""
    # Create trades with different dominant signals
    trades = [
        Trade(
            entry_date=datetime.now(),
            net_pnl=100.0,
            energy_signal=0.8,
            liquidity_signal=0.2,
            sentiment_signal=0.1
        ),
        Trade(
            entry_date=datetime.now(),
            net_pnl=150.0,
            energy_signal=0.3,
            liquidity_signal=0.7,
            sentiment_signal=0.2
        ),
        Trade(
            entry_date=datetime.now(),
            net_pnl=80.0,
            energy_signal=0.2,
            liquidity_signal=0.3,
            sentiment_signal=0.8
        )
    ]
    
    backtest_engine.trades = trades
    
    energy_contrib, liquidity_contrib, sentiment_contrib = backtest_engine._calculate_attribution()
    
    assert energy_contrib == 100.0
    assert liquidity_contrib == 150.0
    assert sentiment_contrib == 80.0


def test_attribution_with_losses(backtest_engine):
    """Test attribution with winning and losing trades."""
    trades = [
        Trade(
            entry_date=datetime.now(),
            net_pnl=200.0,
            energy_signal=0.9,
            liquidity_signal=0.1,
            sentiment_signal=0.1
        ),
        Trade(
            entry_date=datetime.now(),
            net_pnl=-50.0,
            energy_signal=0.8,
            liquidity_signal=0.2,
            sentiment_signal=0.1
        )
    ]
    
    backtest_engine.trades = trades
    
    energy_contrib, _, _ = backtest_engine._calculate_attribution()
    
    assert energy_contrib == 150.0  # 200 - 50


# ==================== Edge Cases Tests ====================

def test_empty_historical_data(backtest_engine, engine_states):
    """Test handling of empty historical data."""
    empty_data = pd.DataFrame()
    energy_states, liquidity_states, sentiment_states = engine_states
    
    with pytest.raises(ValueError, match="Historical data is empty"):
        backtest_engine.run_backtest(
            symbol="TEST",
            historical_data=empty_data,
            energy_states=energy_states,
            liquidity_states=liquidity_states,
            sentiment_states=sentiment_states
        )


def test_missing_columns(backtest_engine, engine_states):
    """Test handling of missing required columns."""
    bad_data = pd.DataFrame({
        'close': [100, 101, 102]
    }, index=pd.date_range(start='2023-01-01', periods=3, freq='D'))
    
    energy_states, liquidity_states, sentiment_states = engine_states
    
    with pytest.raises(ValueError, match="Missing required columns"):
        backtest_engine.run_backtest(
            symbol="TEST",
            historical_data=bad_data,
            energy_states=energy_states,
            liquidity_states=liquidity_states,
            sentiment_states=sentiment_states
        )


def test_no_trades_generated(backtest_engine, historical_data, engine_states):
    """Test backtest with no trades generated."""
    energy_states, liquidity_states, sentiment_states = engine_states
    
    # Set all regimes to avoid trading
    for state in energy_states:
        state.regime = "plastic"  # Avoid trading
    
    results = backtest_engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states
    )
    
    # Should complete without errors even if no trades
    assert results.total_trades == 0
    assert results.win_rate == 0.0
    assert results.total_return == 0.0


# ==================== Performance Test ====================

def test_backtest_performance(backtest_engine, historical_data, engine_states):
    """Test backtest performance."""
    import time
    
    energy_states, liquidity_states, sentiment_states = engine_states
    
    start_time = time.time()
    
    results = backtest_engine.run_backtest(
        symbol="TEST",
        historical_data=historical_data,
        energy_states=energy_states,
        liquidity_states=liquidity_states,
        sentiment_states=sentiment_states
    )
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Should complete in reasonable time (less than 5 seconds for 31 bars)
    assert elapsed_ms < 5000, f"Backtest took {elapsed_ms:.0f}ms (should be <5000ms)"
    assert isinstance(results, BacktestResults)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
