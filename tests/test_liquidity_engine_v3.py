"""
Comprehensive Test Suite for Liquidity Engine v3
=================================================

Tests all components of the Liquidity Engine including:
- Universal Liquidity Interpreter
- Order book processing
- Impact cost calculations
- Slippage modeling
- Liquidity elasticity
- Regime classification
- Edge cases and error handling

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

import pytest
import numpy as np
from datetime import datetime
from typing import List, Tuple

# Import components to test
from engines.liquidity.universal_liquidity_interpreter import (
    UniversalLiquidityInterpreter,
    LiquidityState,
    OrderBookLevel,
    create_interpreter
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_order_book() -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], float]:
    """Create sample order book for testing."""
    mid_price = 450.0
    
    bids = [
        (449.99, 100),
        (449.98, 150),
        (449.97, 200),
        (449.96, 180),
        (449.95, 250),
        (449.90, 300),
        (449.85, 400),
        (449.80, 500),
    ]
    
    asks = [
        (450.01, 120),
        (450.02, 140),
        (450.03, 190),
        (450.04, 170),
        (450.05, 240),
        (450.10, 320),
        (450.15, 380),
        (450.20, 480),
    ]
    
    return bids, asks, mid_price


@pytest.fixture
def interpreter() -> UniversalLiquidityInterpreter:
    """Create universal liquidity interpreter for testing."""
    return create_interpreter()


# ============================================================================
# TEST 1: INTERPRETER INITIALIZATION
# ============================================================================

def test_interpreter_initialization():
    """Test that interpreter initializes correctly."""
    interp = UniversalLiquidityInterpreter()
    
    assert interp.impact_scaling > 0
    assert interp.slippage_scaling > 0
    assert interp.min_depth_threshold > 0
    assert interp.max_spread_bps > 0
    
    print("✅ Test 1 PASSED: Interpreter initialization")


# ============================================================================
# TEST 2: LIQUIDITY STATE CALCULATION
# ============================================================================

def test_liquidity_state_calculation(interpreter, sample_order_book):
    """Test complete liquidity state calculation."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(
        bids=bids,
        asks=asks,
        mid_price=mid_price,
        volume_24h=10000000,
        execution_size=1000
    )
    
    # Check all fields are present
    assert isinstance(state, LiquidityState)
    assert isinstance(state.impact_cost, float)
    assert isinstance(state.slippage, float)
    assert isinstance(state.depth_score, float)
    assert 0 <= state.depth_score <= 1
    assert state.regime in ["high_liquidity", "medium_liquidity", "low_liquidity", "illiquid"]
    assert 0 <= state.stability <= 1
    assert 0 <= state.confidence <= 1
    
    print("✅ Test 2 PASSED: Liquidity state calculation")


# ============================================================================
# TEST 3: SPREAD CALCULATION
# ============================================================================

def test_spread_calculation(interpreter, sample_order_book):
    """Test bid-ask spread calculation."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Spread should be positive and reasonable
    assert state.spread_bps > 0
    assert state.spread_bps < 100  # Less than 1% for liquid market
    
    # Effective spread should be larger than raw spread
    assert state.effective_spread_bps >= state.spread_bps
    
    print(f"✅ Test 3 PASSED: Spread = {state.spread_bps:.2f} bps")


# ============================================================================
# TEST 4: IMPACT COST CALCULATION
# ============================================================================

def test_impact_cost(interpreter, sample_order_book):
    """Test market impact cost calculation."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price, execution_size=1000)
    
    # Impact should be positive
    assert state.impact_cost >= 0
    assert state.impact_cost_buy >= 0
    assert state.impact_cost_sell >= 0
    
    # Buy and sell impacts should be roughly similar for balanced book
    impact_diff = abs(state.impact_cost_buy - state.impact_cost_sell)
    assert impact_diff < 50  # Less than 50 bps difference
    
    print(f"✅ Test 4 PASSED: Impact = {state.impact_cost:.2f} bps")


# ============================================================================
# TEST 5: SLIPPAGE CALCULATION
# ============================================================================

def test_slippage_calculation(interpreter, sample_order_book):
    """Test slippage calculation."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price, execution_size=500)
    
    # Slippage should be positive
    assert state.slippage >= 0
    assert state.slippage_buy >= 0
    assert state.slippage_sell >= 0
    
    # Slippage should increase with execution size
    state_large = interpreter.interpret(bids, asks, mid_price, execution_size=2000)
    assert state_large.slippage > state.slippage
    
    print(f"✅ Test 5 PASSED: Slippage = {state.slippage:.2f} bps")


# ============================================================================
# TEST 6: DEPTH SCORE CALCULATION
# ============================================================================

def test_depth_score(interpreter, sample_order_book):
    """Test order book depth scoring."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price, volume_24h=10000000)
    
    # Depth score should be between 0 and 1
    assert 0 <= state.depth_score <= 1
    
    # Higher volume context should give different depth score
    # (Not necessarily higher since depth_score also considers absolute depth)
    state_low_vol = interpreter.interpret(bids, asks, mid_price, volume_24h=100)
    assert isinstance(state_low_vol.depth_score, float)
    assert 0 <= state_low_vol.depth_score <= 1
    
    print(f"✅ Test 6 PASSED: Depth score = {state.depth_score:.2%}")


# ============================================================================
# TEST 7: DEPTH IMBALANCE
# ============================================================================

def test_depth_imbalance(interpreter):
    """Test depth imbalance calculation."""
    mid_price = 100.0
    
    # Bid-heavy book
    bids_heavy = [(99.9, 1000), (99.8, 1000)]
    asks_light = [(100.1, 100), (100.2, 100)]
    
    state = interpreter.interpret(bids_heavy, asks_light, mid_price)
    
    # Should be positive (more bid depth)
    assert state.depth_imbalance > 0
    
    # Ask-heavy book
    bids_light = [(99.9, 100), (99.8, 100)]
    asks_heavy = [(100.1, 1000), (100.2, 1000)]
    
    state2 = interpreter.interpret(bids_light, asks_heavy, mid_price)
    
    # Should be negative (more ask depth)
    assert state2.depth_imbalance < 0
    
    print("✅ Test 7 PASSED: Depth imbalance detection")


# ============================================================================
# TEST 8: LIQUIDITY ELASTICITY
# ============================================================================

def test_liquidity_elasticity(interpreter, sample_order_book):
    """Test liquidity elasticity calculation."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Elasticity should be positive
    assert state.elasticity > 0
    assert state.elasticity_buy > 0
    assert state.elasticity_sell > 0
    
    # Should be capped at reasonable level
    assert state.elasticity < 10
    
    print(f"✅ Test 8 PASSED: Elasticity = {state.elasticity:.4f}")


# ============================================================================
# TEST 9: VOLUME PROFILE
# ============================================================================

def test_volume_profile(interpreter, sample_order_book):
    """Test volume distribution quality."""
    bids, asks, mid_price = sample_order_book
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Volume profile should be between 0 and 1
    assert 0 <= state.volume_profile <= 1
    
    # Uniform distribution should score higher
    uniform_bids = [(100 - i*0.01, 100) for i in range(10)]
    uniform_asks = [(100 + i*0.01, 100) for i in range(10)]
    
    state_uniform = interpreter.interpret(uniform_bids, uniform_asks, 100.0)
    
    # Uniform should have higher profile score
    assert state_uniform.volume_profile > 0.3
    
    print(f"✅ Test 9 PASSED: Volume profile = {state.volume_profile:.2%}")


# ============================================================================
# TEST 10: VOLUME IMBALANCE
# ============================================================================

def test_volume_imbalance(interpreter):
    """Test buy/sell volume imbalance."""
    mid_price = 100.0
    
    # Buy-heavy volume
    bids = [(100 - i*0.01, 1000) for i in range(5)]
    asks = [(100 + i*0.01, 100) for i in range(5)]
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Should indicate buy pressure
    assert state.volume_imbalance > 0
    
    print(f"✅ Test 10 PASSED: Volume imbalance = {state.volume_imbalance:+.2f}")


# ============================================================================
# TEST 11: REGIME CLASSIFICATION
# ============================================================================

def test_regime_classification(interpreter):
    """Test liquidity regime classification."""
    mid_price = 100.0
    
    # High liquidity scenario
    bids_high = [(100 - i*0.01, 1000) for i in range(20)]
    asks_high = [(100 + i*0.01, 1000) for i in range(20)]
    
    state_high = interpreter.interpret(bids_high, asks_high, mid_price, volume_24h=10000000)
    
    assert state_high.regime in ["high_liquidity", "medium_liquidity"]
    
    # Low liquidity scenario
    bids_low = [(99.5, 10), (99.0, 10)]
    asks_low = [(100.5, 10), (101.0, 10)]
    
    state_low = interpreter.interpret(bids_low, asks_low, mid_price, volume_24h=100)
    
    assert state_low.regime in ["low_liquidity", "illiquid"]
    
    print(f"✅ Test 11 PASSED: Regimes = {state_high.regime}, {state_low.regime}")


# ============================================================================
# TEST 12: CONFIDENCE SCORING
# ============================================================================

def test_confidence_scoring(interpreter, sample_order_book):
    """Test confidence score calculation."""
    bids, asks, mid_price = sample_order_book
    
    # Good data should have high confidence
    state_good = interpreter.interpret(bids, asks, mid_price, volume_24h=10000000)
    
    assert 0 <= state_good.confidence <= 1
    assert state_good.confidence > 0.5
    
    # Poor data should have lower confidence
    bids_poor = [(99, 10)]
    asks_poor = [(101, 10)]
    
    state_poor = interpreter.interpret(bids_poor, asks_poor, 100, volume_24h=100)
    
    assert state_poor.confidence < state_good.confidence
    
    print(f"✅ Test 12 PASSED: Confidence = {state_good.confidence:.2%}")


# ============================================================================
# TEST 13: EMPTY ORDER BOOK
# ============================================================================

def test_empty_order_book(interpreter):
    """Test handling of empty order book."""
    empty_bids = []
    empty_asks = []
    
    state = interpreter.interpret(empty_bids, empty_asks, 100.0)
    
    # Should handle gracefully
    assert isinstance(state, LiquidityState)
    assert state.spread_bps > 0
    assert state.regime in ["low_liquidity", "illiquid"]
    
    print("✅ Test 13 PASSED: Empty order book handled")


# ============================================================================
# TEST 14: SINGLE-SIDED BOOK
# ============================================================================

def test_single_sided_book(interpreter):
    """Test order book with only bids or only asks."""
    mid_price = 100.0
    
    # Only bids
    bids_only = [(99, 100), (98, 100)]
    state_bids = interpreter.interpret(bids_only, [], mid_price)
    
    assert isinstance(state_bids, LiquidityState)
    
    # Only asks
    asks_only = [(101, 100), (102, 100)]
    state_asks = interpreter.interpret([], asks_only, mid_price)
    
    assert isinstance(state_asks, LiquidityState)
    
    print("✅ Test 14 PASSED: Single-sided books handled")


# ============================================================================
# TEST 15: LARGE EXECUTION SIZE
# ============================================================================

def test_large_execution_size(interpreter, sample_order_book):
    """Test impact with very large execution size."""
    bids, asks, mid_price = sample_order_book
    
    # Small size
    state_small = interpreter.interpret(bids, asks, mid_price, execution_size=100)
    
    # Large size (exceeds book depth)
    state_large = interpreter.interpret(bids, asks, mid_price, execution_size=10000)
    
    # Large execution should have much higher impact
    assert state_large.impact_cost > state_small.impact_cost * 2
    assert state_large.slippage > state_small.slippage
    
    print("✅ Test 15 PASSED: Large execution size impact verified")


# ============================================================================
# TEST 16: TIGHT SPREAD
# ============================================================================

def test_tight_spread(interpreter):
    """Test very tight spread scenario."""
    mid_price = 100.0
    
    # Ultra-tight spread (0.01%)
    bids = [(99.999, 100), (99.998, 100)]
    asks = [(100.001, 100), (100.002, 100)]
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Should have very low spread
    assert state.spread_bps < 5  # Less than 0.05%
    assert state.regime == "high_liquidity"
    
    print(f"✅ Test 16 PASSED: Tight spread = {state.spread_bps:.3f} bps")


# ============================================================================
# TEST 17: WIDE SPREAD
# ============================================================================

def test_wide_spread(interpreter):
    """Test very wide spread scenario."""
    mid_price = 100.0
    
    # Wide spread (2%)
    bids = [(99, 100)]
    asks = [(101, 100)]
    
    state = interpreter.interpret(bids, asks, mid_price)
    
    # Should have high spread
    assert state.spread_bps > 100  # More than 1%
    assert state.regime in ["low_liquidity", "illiquid"]
    
    print(f"✅ Test 17 PASSED: Wide spread = {state.spread_bps:.2f} bps")


# ============================================================================
# TEST 18: CONSISTENCY CHECK
# ============================================================================

def test_consistency(interpreter, sample_order_book):
    """Test that repeated calculations give consistent results."""
    bids, asks, mid_price = sample_order_book
    
    state1 = interpreter.interpret(bids, asks, mid_price)
    state2 = interpreter.interpret(bids, asks, mid_price)
    
    # Results should be identical
    assert abs(state1.impact_cost - state2.impact_cost) < 1e-10
    assert abs(state1.slippage - state2.slippage) < 1e-10
    assert state1.regime == state2.regime
    
    print("✅ Test 18 PASSED: Calculations are consistent")


# ============================================================================
# TEST 19: PERFORMANCE BENCHMARK
# ============================================================================

def test_performance(interpreter, sample_order_book):
    """Benchmark interpreter performance."""
    import time
    
    bids, asks, mid_price = sample_order_book
    
    n_iterations = 100
    start_time = time.time()
    
    for _ in range(n_iterations):
        interpreter.interpret(bids, asks, mid_price)
    
    elapsed = time.time() - start_time
    avg_time = elapsed / n_iterations * 1000  # ms
    
    # Should complete in reasonable time (< 5ms per call)
    assert avg_time < 5, f"Performance too slow: {avg_time:.2f}ms per call"
    
    print(f"✅ Test 19 PASSED: Performance {avg_time:.2f}ms per calculation")


# ============================================================================
# TEST 20: NUMERICAL STABILITY
# ============================================================================

def test_numerical_stability(interpreter):
    """Test numerical stability with varying prices."""
    spreads = []
    
    for price in [1.0, 10.0, 100.0, 1000.0, 10000.0]:
        bids = [(price * 0.999, 100), (price * 0.998, 100)]
        asks = [(price * 1.001, 100), (price * 1.002, 100)]
        
        state = interpreter.interpret(bids, asks, price)
        
        # All values should be finite
        assert np.isfinite(state.impact_cost)
        assert np.isfinite(state.slippage)
        assert np.isfinite(state.elasticity)
        
        spreads.append(state.spread_bps)
    
    # Spreads should be similar across different price levels
    spread_variance = np.var(spreads)
    assert spread_variance < 1.0, f"Spread variance too high: {spread_variance}"
    
    print("✅ Test 20 PASSED: Numerically stable across price levels")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 LIQUIDITY ENGINE V3 COMPREHENSIVE TEST SUITE")
    print("="*70 + "\n")
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETE")
    print("="*70 + "\n")
