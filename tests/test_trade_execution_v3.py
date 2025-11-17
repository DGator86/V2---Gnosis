"""
Comprehensive Test Suite for Universal Policy Composer v3
==========================================================

Tests the Multi-Engine Trade Orchestration System.

Test Coverage:
1. Signal extraction from each engine (3 tests)
2. Composite signal calculation (2 tests)
3. Direction determination (3 tests)
4. Position sizing algorithms (5 tests)
5. Entry/exit level calculation (2 tests)
6. Execution cost estimation (2 tests)
7. Monte Carlo simulation (3 tests)
8. Trade idea validation (3 tests)
9. Edge cases (2 tests)

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import the Universal Policy Composer
from engines.composer.universal_policy_composer import (
    UniversalPolicyComposer,
    TradeDirection,
    PositionSizeMethod,
    RiskParameters,
    TradeIdea,
    MonteCarloResult
)


# ==================== Mock Data Classes ====================

@dataclass
class MockEnergyState:
    """Mock energy state for testing."""
    movement_energy: float = 100.0
    movement_energy_up: float = 105.0
    movement_energy_down: float = 95.0
    elasticity: float = 0.5
    elasticity_up: float = 0.55
    elasticity_down: float = 0.45
    energy_asymmetry: float = 10.0  # Positive = easier up
    elasticity_asymmetry: float = 0.1
    gamma_force: float = 0.05
    vanna_force: float = 0.02
    charm_force: float = 0.01
    regime: str = "elastic"
    stability: float = 0.9
    timestamp: datetime = datetime.now()
    confidence: float = 0.95


@dataclass
class MockLiquidityState:
    """Mock liquidity state for testing."""
    impact_cost: float = 10.0  # 10 bps
    impact_cost_buy: float = 12.0
    impact_cost_sell: float = 8.0
    slippage: float = 5.0  # 5 bps
    slippage_buy: float = 6.0
    slippage_sell: float = 4.0
    depth_score: float = 0.8
    depth_imbalance: float = 0.2  # Positive = more bids
    spread_bps: float = 2.0
    liquidity_elasticity: float = 0.7
    regime: str = "liquid"
    stability: float = 0.85
    timestamp: datetime = datetime.now()
    confidence: float = 0.90


@dataclass
class MockSentimentState:
    """Mock sentiment state for testing."""
    sentiment_score: float = 0.6  # Bullish
    sentiment_magnitude: float = 0.6
    sentiment_momentum: float = 0.1
    sentiment_acceleration: float = 0.02
    contrarian_signal: float = -0.4  # Fade bullish sentiment
    crowd_conviction: float = 0.7
    sentiment_energy: float = 0.42
    regime: str = "bullish"
    stability: float = 0.88
    timestamp: datetime = datetime.now()
    confidence: float = 0.92


# ==================== Test Fixtures ====================

@pytest.fixture
def composer():
    """Create UniversalPolicyComposer instance."""
    return UniversalPolicyComposer(
        risk_params=RiskParameters(),
        energy_weight=0.4,
        liquidity_weight=0.3,
        sentiment_weight=0.3,
        enable_monte_carlo=True,
        mc_simulations=100  # Reduced for testing speed
    )


@pytest.fixture
def energy_state():
    """Create mock energy state."""
    return MockEnergyState()


@pytest.fixture
def liquidity_state():
    """Create mock liquidity state."""
    return MockLiquidityState()


@pytest.fixture
def sentiment_state():
    """Create mock sentiment state."""
    return MockSentimentState()


# ==================== Signal Extraction Tests ====================

def test_extract_energy_signal_bullish(composer, energy_state):
    """Test energy signal extraction for bullish setup."""
    # Positive asymmetry = easier up = bullish
    energy_state.energy_asymmetry = 50.0
    energy_state.elasticity_asymmetry = -5.0  # Less resistance up
    
    signal = composer._extract_energy_signal(energy_state)
    
    assert -1.0 <= signal <= 1.0, "Signal should be in range [-1, 1]"
    assert signal > 0, "Positive asymmetry should give bullish signal"
    assert signal <= 1.0, "Signal should not exceed 1.0"


def test_extract_liquidity_signal_bullish(composer, liquidity_state):
    """Test liquidity signal extraction for bullish setup."""
    # Positive depth imbalance = more bids = bullish
    liquidity_state.depth_imbalance = 0.5
    liquidity_state.impact_cost = 5.0  # Low impact
    
    signal = composer._extract_liquidity_signal(liquidity_state)
    
    assert -1.0 <= signal <= 1.0, "Signal should be in range [-1, 1]"
    assert signal > 0, "Positive depth imbalance should give bullish signal"


def test_extract_sentiment_signal_contrarian(composer, sentiment_state):
    """Test sentiment signal extraction for contrarian setup."""
    # High bullish sentiment = contrarian bearish
    sentiment_state.sentiment_score = 0.8
    sentiment_state.contrarian_signal = -0.6
    sentiment_state.crowd_conviction = 0.8
    
    signal = composer._extract_sentiment_signal(sentiment_state)
    
    assert -1.0 <= signal <= 1.0, "Signal should be in range [-1, 1]"
    # Contrarian signal should dominate (70% weight)
    assert signal < 0, "High bullish sentiment should give bearish contrarian signal"


# ==================== Composite Signal Tests ====================

def test_compute_composite_signal_bullish(composer):
    """Test composite signal with all bullish inputs."""
    energy_signal = 0.6
    liquidity_signal = 0.4
    sentiment_signal = 0.3
    
    composite = composer._compute_composite_signal(
        energy_signal, liquidity_signal, sentiment_signal
    )
    
    assert -1.0 <= composite <= 1.0, "Composite should be in range [-1, 1]"
    assert composite > 0, "All positive signals should give positive composite"
    
    # Check weighted average
    expected = 0.4 * 0.6 + 0.3 * 0.4 + 0.3 * 0.3
    assert abs(composite - expected) < 0.01, "Composite should match weighted average"


def test_compute_composite_signal_mixed(composer):
    """Test composite signal with mixed inputs."""
    energy_signal = 0.5
    liquidity_signal = -0.3
    sentiment_signal = 0.2
    
    composite = composer._compute_composite_signal(
        energy_signal, liquidity_signal, sentiment_signal
    )
    
    assert -1.0 <= composite <= 1.0, "Composite should be in range [-1, 1]"
    # Energy has highest weight (0.4), so should still be positive
    assert composite > 0, "Positive energy signal should dominate"


# ==================== Direction Determination Tests ====================

def test_determine_direction_long(composer, energy_state, liquidity_state, sentiment_state):
    """Test direction determination for LONG."""
    composite_signal = 0.5  # Strong bullish
    
    direction = composer._determine_direction(
        composite_signal, energy_state, liquidity_state, sentiment_state
    )
    
    assert direction == TradeDirection.LONG, "Strong positive signal should give LONG"


def test_determine_direction_short(composer, energy_state, liquidity_state, sentiment_state):
    """Test direction determination for SHORT."""
    composite_signal = -0.6  # Strong bearish
    
    direction = composer._determine_direction(
        composite_signal, energy_state, liquidity_state, sentiment_state
    )
    
    assert direction == TradeDirection.SHORT, "Strong negative signal should give SHORT"


def test_determine_direction_avoid_bad_regime(composer, energy_state, liquidity_state, sentiment_state):
    """Test direction determination avoids bad regimes."""
    composite_signal = 0.8  # Strong signal
    energy_state.regime = "plastic"  # Bad regime
    
    direction = composer._determine_direction(
        composite_signal, energy_state, liquidity_state, sentiment_state
    )
    
    assert direction == TradeDirection.AVOID, "Should AVOID plastic energy regime"


# ==================== Position Sizing Tests ====================

def test_kelly_criterion_size(composer):
    """Test Kelly Criterion position sizing."""
    # Create winning historical returns
    historical_returns = [0.01, -0.005, 0.015, -0.003, 0.02, 0.008, -0.004, 0.012]
    
    kelly_shares, kelly_frac = composer._kelly_criterion_size(
        historical_returns=historical_returns,
        account_value=100000.0,
        current_price=100.0
    )
    
    assert kelly_shares >= 0, "Kelly shares should be non-negative"
    assert 0 <= kelly_frac <= 1.0, "Kelly fraction should be in [0, 1]"


def test_vol_target_size(composer):
    """Test volatility targeting position sizing."""
    volatility = 0.30  # 30% annualized vol
    account_value = 100000.0
    current_price = 100.0
    
    shares = composer._vol_target_size(volatility, account_value, current_price)
    
    assert shares >= 0, "Shares should be non-negative"
    # Higher vol should give smaller position
    assert shares < account_value / current_price, "Vol target should reduce position"


def test_energy_aware_size_high_energy(composer):
    """Test energy-aware sizing reduces position for high energy."""
    base_size = 100.0
    high_energy = 2000.0  # Above max_movement_energy (1000)
    elasticity = 0.5
    
    adjusted = composer._energy_aware_size(base_size, high_energy, elasticity)
    
    assert adjusted < base_size, "High energy should reduce position"
    assert adjusted >= 0, "Adjusted size should be non-negative"


def test_energy_aware_size_low_elasticity(composer):
    """Test energy-aware sizing reduces position for low elasticity."""
    base_size = 100.0
    energy = 500.0
    low_elasticity = 0.05  # Below min_elasticity (0.1)
    
    adjusted = composer._energy_aware_size(base_size, energy, low_elasticity)
    
    assert adjusted < base_size, "Low elasticity should reduce position"
    assert adjusted >= 0, "Adjusted size should be non-negative"


def test_calculate_position_size_integration(composer, energy_state, liquidity_state):
    """Test full position size calculation integration."""
    direction = TradeDirection.LONG
    current_price = 100.0
    account_value = 100000.0
    volatility = 0.20
    
    position_size, method, kelly_frac = composer._calculate_position_size(
        direction=direction,
        current_price=current_price,
        account_value=account_value,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        volatility=volatility,
        historical_returns=None
    )
    
    assert position_size >= 0, "Position size should be non-negative"
    assert isinstance(method, PositionSizeMethod), "Method should be PositionSizeMethod enum"
    assert position_size * current_price <= account_value, "Position should not exceed account"


# ==================== Entry/Exit Level Tests ====================

def test_determine_entry_range_long(composer, liquidity_state):
    """Test entry range for LONG direction."""
    current_price = 100.0
    direction = TradeDirection.LONG
    
    entry, entry_min, entry_max = composer._determine_entry_range(
        current_price, direction, liquidity_state
    )
    
    assert entry_min <= entry <= entry_max, "Entry should be within range"
    assert entry_max > current_price, "LONG max should allow paying up"


def test_calculate_exit_levels_long(composer):
    """Test stop loss and take profit for LONG."""
    entry_price = 100.0
    direction = TradeDirection.LONG
    
    stop_loss, take_profit = composer._calculate_exit_levels(entry_price, direction)
    
    assert stop_loss < entry_price, "Stop loss should be below entry for LONG"
    assert take_profit > entry_price, "Take profit should be above entry for LONG"
    assert (take_profit - entry_price) > (entry_price - stop_loss), "R/R should be > 1"


# ==================== Execution Cost Tests ====================

def test_estimate_execution_costs(composer, liquidity_state):
    """Test execution cost estimation."""
    position_size = 100.0
    current_price = 100.0
    
    slippage, impact, total = composer._estimate_execution_costs(
        position_size, current_price, liquidity_state
    )
    
    assert slippage >= 0, "Slippage should be non-negative"
    assert impact >= 0, "Impact should be non-negative"
    assert total >= slippage, "Total should include slippage"
    assert total >= impact, "Total should include impact"


def test_execution_costs_increase_with_size(composer, liquidity_state):
    """Test execution costs increase with position size."""
    small_size = 10.0
    large_size = 1000.0
    current_price = 100.0
    
    small_slippage, small_impact, small_total = composer._estimate_execution_costs(
        small_size, current_price, liquidity_state
    )
    
    large_slippage, large_impact, large_total = composer._estimate_execution_costs(
        large_size, current_price, liquidity_state
    )
    
    assert large_total > small_total, "Larger position should have higher costs"


# ==================== Monte Carlo Tests ====================

def test_monte_carlo_simulation_basic(composer):
    """Test basic Monte Carlo simulation."""
    entry_price = 100.0
    target_price = 106.0  # 6% profit target
    stop_price = 98.0  # 2% stop loss
    volatility = 0.20
    
    mc_result = composer._run_monte_carlo(
        entry_price, target_price, stop_price, volatility, num_simulations=100
    )
    
    assert isinstance(mc_result, MonteCarloResult), "Should return MonteCarloResult"
    assert 0 <= mc_result.win_rate <= 1.0, "Win rate should be in [0, 1]"
    assert mc_result.num_simulations == 100, "Should match requested simulations"
    assert len(mc_result.pnl_distribution) == 100, "Should have 100 P&L results"


def test_monte_carlo_statistics(composer):
    """Test Monte Carlo statistics are reasonable."""
    entry_price = 100.0
    target_price = 110.0
    stop_price = 95.0
    volatility = 0.25
    
    mc_result = composer._run_monte_carlo(
        entry_price, target_price, stop_price, volatility, num_simulations=100
    )
    
    assert mc_result.max_profit > 0, "Should have some profitable outcomes"
    assert mc_result.max_loss < 0, "Should have some losing outcomes"
    assert mc_result.var_95 <= 0, "VaR should be negative (loss)"
    assert mc_result.cvar_95 <= mc_result.var_95, "CVaR should be worse than VaR"


def test_monte_carlo_profit_factor(composer):
    """Test Monte Carlo profit factor calculation."""
    entry_price = 100.0
    target_price = 106.0
    stop_price = 98.0
    volatility = 0.15  # Lower vol for more consistent results
    
    mc_result = composer._run_monte_carlo(
        entry_price, target_price, stop_price, volatility, num_simulations=100
    )
    
    assert mc_result.profit_factor >= 0, "Profit factor should be non-negative"


# ==================== Trade Idea Validation Tests ====================

def test_validate_trade_idea_valid(composer, energy_state, liquidity_state, sentiment_state):
    """Test validation of valid trade idea."""
    is_valid, warnings, errors = composer._validate_trade_idea(
        direction=TradeDirection.LONG,
        position_size=100.0,
        position_value=10000.0,
        account_value=100000.0,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        expected_impact=10.0,
        expected_slippage=5.0
    )
    
    assert is_valid, "Valid trade should pass validation"
    assert isinstance(warnings, list), "Warnings should be a list"
    assert isinstance(errors, list), "Errors should be a list"


def test_validate_trade_idea_oversized(composer, energy_state, liquidity_state, sentiment_state):
    """Test validation catches oversized positions."""
    is_valid, warnings, errors = composer._validate_trade_idea(
        direction=TradeDirection.LONG,
        position_size=1000.0,
        position_value=100000.0,  # 100% of account
        account_value=100000.0,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        expected_impact=10.0,
        expected_slippage=5.0
    )
    
    assert not is_valid, "Oversized position should fail validation"
    assert len(errors) > 0, "Should have validation errors"


def test_validate_trade_idea_bad_regime(composer, energy_state, liquidity_state, sentiment_state):
    """Test validation catches bad regimes."""
    energy_state.regime = "plastic"
    
    is_valid, warnings, errors = composer._validate_trade_idea(
        direction=TradeDirection.LONG,
        position_size=100.0,
        position_value=10000.0,
        account_value=100000.0,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        expected_impact=10.0,
        expected_slippage=5.0
    )
    
    assert not is_valid, "Plastic regime should fail validation"
    assert any("plastic" in e.lower() for e in errors), "Should mention plastic regime"


# ==================== Full Integration Tests ====================

def test_compose_trade_idea_integration(composer, energy_state, liquidity_state, sentiment_state):
    """Test full trade idea composition integration."""
    symbol = "AAPL"
    current_price = 150.0
    account_value = 100000.0
    current_volatility = 0.25
    
    trade_idea = composer.compose_trade_idea(
        symbol=symbol,
        current_price=current_price,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        account_value=account_value,
        current_volatility=current_volatility,
        historical_returns=None
    )
    
    assert isinstance(trade_idea, TradeIdea), "Should return TradeIdea"
    assert trade_idea.symbol == symbol, "Symbol should match"
    assert trade_idea.direction in TradeDirection, "Direction should be valid"
    assert trade_idea.position_size >= 0, "Position size should be non-negative"
    assert trade_idea.entry_price > 0, "Entry price should be positive"
    assert -1.0 <= trade_idea.composite_signal <= 1.0, "Composite signal in range"


def test_compose_trade_idea_with_historical_returns(composer, energy_state, liquidity_state, sentiment_state):
    """Test trade idea composition with historical returns for Kelly."""
    symbol = "MSFT"
    current_price = 300.0
    account_value = 200000.0
    current_volatility = 0.30
    
    # Create profitable historical returns
    historical_returns = [0.02, -0.01, 0.03, 0.01, -0.005, 0.025, 0.01, -0.008]
    
    trade_idea = composer.compose_trade_idea(
        symbol=symbol,
        current_price=current_price,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        account_value=account_value,
        current_volatility=current_volatility,
        historical_returns=historical_returns
    )
    
    assert trade_idea.kelly_fraction >= 0, "Kelly fraction should be calculated"


# ==================== Edge Case Tests ====================

def test_compose_trade_idea_zero_volatility(composer, energy_state, liquidity_state, sentiment_state):
    """Test handling of zero volatility."""
    symbol = "TEST"
    current_price = 50.0
    account_value = 50000.0
    current_volatility = 0.0  # Zero volatility edge case
    
    trade_idea = composer.compose_trade_idea(
        symbol=symbol,
        current_price=current_price,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        account_value=account_value,
        current_volatility=current_volatility,
        historical_returns=None
    )
    
    assert isinstance(trade_idea, TradeIdea), "Should handle zero volatility"
    assert trade_idea.position_size >= 0, "Should still calculate position"


def test_regime_consistency_aligned(composer, energy_state, liquidity_state, sentiment_state):
    """Test regime consistency with aligned regimes."""
    # All bullish regimes
    energy_state.regime = "super_elastic"
    liquidity_state.regime = "deep"
    sentiment_state.regime = "extreme_bullish"
    
    consistency = composer._check_regime_consistency(
        energy_state, liquidity_state, sentiment_state
    )
    
    assert 0 <= consistency <= 1.0, "Consistency should be in [0, 1]"
    assert consistency > 0.7, "Aligned regimes should have high consistency"


# ==================== Performance Test ====================

def test_compose_trade_idea_performance(composer, energy_state, liquidity_state, sentiment_state):
    """Test performance of trade idea composition."""
    import time
    
    symbol = "PERF"
    current_price = 100.0
    account_value = 100000.0
    current_volatility = 0.20
    
    start_time = time.time()
    
    trade_idea = composer.compose_trade_idea(
        symbol=symbol,
        current_price=current_price,
        energy_state=energy_state,
        liquidity_state=liquidity_state,
        sentiment_state=sentiment_state,
        account_value=account_value,
        current_volatility=current_volatility,
        historical_returns=None
    )
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    assert elapsed_ms < 500, f"Should complete in <500ms (took {elapsed_ms:.1f}ms)"
    assert isinstance(trade_idea, TradeIdea), "Should return valid trade idea"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
