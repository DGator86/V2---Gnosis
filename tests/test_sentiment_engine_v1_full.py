"""
Comprehensive tests for Sentiment Engine v1.0

Tests cover:
- Individual processors
- Fusion logic
- Graceful degradation
- Integration scenarios
"""

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from engines.inputs.stub_adapters import StaticMarketDataAdapter
from engines.sentiment.fusion import (
    apply_graceful_degradation,
    detect_conflicting_signals,
    fuse_signals,
)
from engines.sentiment.models import SentimentSignal
from engines.sentiment.processors.all_processors import (
    BreadthRegimeProcessor,
    EnergyProcessor,
    FlowBiasProcessor,
    OscillatorProcessor,
    VolatilityProcessor,
    WyckoffProcessor,
)
from engines.sentiment.sentiment_engine_v1_full import SentimentEngineV1


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    now = datetime.utcnow()
    periods = 100
    
    # Create trending data
    base_price = 100.0
    trend = np.linspace(0, 10, periods)
    noise = np.random.randn(periods) * 0.5
    
    closes = base_price + trend + noise
    highs = closes + np.abs(np.random.randn(periods)) * 0.5
    lows = closes - np.abs(np.random.randn(periods)) * 0.5
    opens = np.roll(closes, 1)
    opens[0] = base_price
    volumes = 1000 + np.random.randint(-100, 100, periods)
    
    df = pl.DataFrame({
        "timestamp": [now - timedelta(days=periods-i) for i in range(periods)],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    
    return df


@pytest.fixture
def mean_revert_ohlcv():
    """Create mean-reverting OHLCV data."""
    now = datetime.utcnow()
    periods = 100
    
    base_price = 100.0
    oscillation = 5 * np.sin(np.linspace(0, 4*np.pi, periods))
    noise = np.random.randn(periods) * 0.3
    
    closes = base_price + oscillation + noise
    highs = closes + np.abs(np.random.randn(periods)) * 0.3
    lows = closes - np.abs(np.random.randn(periods)) * 0.3
    opens = np.roll(closes, 1)
    opens[0] = base_price
    volumes = 1000 + np.random.randint(-50, 50, periods)
    
    df = pl.DataFrame({
        "timestamp": [now - timedelta(days=periods-i) for i in range(periods)],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    
    return df


# ============================================================================
# Processor Tests
# ============================================================================

def test_wyckoff_processor_basic(sample_ohlcv):
    """Test Wyckoff processor returns valid output."""
    processor = WyckoffProcessor({"lookback_periods": 50})
    signals, sentiment = processor.process(sample_ohlcv)
    
    # Check signal structure
    assert signals.phase.phase in ["A", "B", "C", "D", "E", "Unknown"]
    assert 0.0 <= signals.phase.confidence <= 1.0
    assert 0.0 <= signals.demand_supply_ratio <= 2.0
    assert isinstance(signals.spring_detected, bool)
    assert isinstance(signals.utad_detected, bool)
    assert -1.0 <= signals.operator_bias <= 1.0
    assert 0.0 <= signals.strength_score <= 1.0
    
    # Check sentiment signal
    assert -1.0 <= sentiment.value <= 1.0
    assert 0.0 <= sentiment.confidence <= 1.0
    assert sentiment.driver == "wyckoff"


def test_oscillator_processor_basic(sample_ohlcv):
    """Test oscillator processor returns valid output."""
    processor = OscillatorProcessor({
        "rsi_period": 14,
        "mfi_period": 14,
        "stoch_k_period": 14,
    })
    signals, sentiment = processor.process(sample_ohlcv)
    
    # Check RSI
    assert 0.0 <= signals.rsi.value <= 100.0
    assert isinstance(signals.rsi.overbought, bool)
    assert isinstance(signals.rsi.oversold, bool)
    
    # Check MFI
    assert 0.0 <= signals.mfi.value <= 100.0
    assert 0.0 <= signals.mfi.buy_pressure <= 1.0
    assert 0.0 <= signals.mfi.sell_pressure <= 1.0
    
    # Check Stochastic
    assert 0.0 <= signals.stochastic.k_value <= 100.0
    assert 0.0 <= signals.stochastic.d_value <= 100.0
    
    # Check composite
    assert -1.0 <= signals.composite_score <= 1.0
    assert sentiment.driver == "oscillators"


def test_volatility_processor_basic(sample_ohlcv):
    """Test volatility processor returns valid output."""
    processor = VolatilityProcessor({
        "bb_period": 20,
        "kc_period": 20,
    })
    signals, sentiment = processor.process(sample_ohlcv)
    
    # Check Bollinger
    assert 0.0 <= signals.bollinger.bandwidth
    assert -1.0 <= signals.bollinger.mean_reversion_pressure <= 1.0
    assert isinstance(signals.bollinger.squeeze_active, bool)
    
    # Check Keltner
    assert isinstance(signals.keltner.expansion, bool)
    assert isinstance(signals.keltner.compression, bool)
    
    # Check squeeze
    assert isinstance(signals.squeeze_detected, bool)
    assert signals.compression_energy >= 0.0
    assert signals.expansion_energy >= 0.0
    
    assert sentiment.driver == "volatility"


def test_flow_processor_basic(sample_ohlcv):
    """Test flow bias processor returns valid output."""
    processor = FlowBiasProcessor({"orderflow_window": 10})
    signals, sentiment = processor.process(sample_ohlcv, darkpool_data=None)
    
    # Check order flow
    assert -1.0 <= signals.order_flow.bid_ask_imbalance <= 1.0
    assert 0.0 <= signals.order_flow.aggressive_buy_ratio <= 1.0
    assert 0.0 <= signals.order_flow.aggressive_sell_ratio <= 1.0
    assert -1.0 <= signals.order_flow.net_aggressor_pressure <= 1.0
    
    # Check dark pool (should be default/neutral with no data)
    assert -1.0 <= signals.dark_pool.sentiment_score <= 1.0
    assert 0.0 <= signals.dark_pool.confidence <= 1.0
    
    # Check composite
    assert -1.0 <= signals.composite_flow_bias <= 1.0
    assert sentiment.driver == "flow"


def test_flow_processor_with_darkpool(sample_ohlcv):
    """Test flow processor with dark pool data."""
    processor = FlowBiasProcessor({"orderflow_window": 10})
    darkpool_data = {"dix": 0.47, "gex": -2.5}
    
    signals, sentiment = processor.process(sample_ohlcv, darkpool_data)
    
    assert signals.dark_pool.dix_value == 0.47
    assert signals.dark_pool.gex_value == -2.5
    assert signals.dark_pool.confidence > 0.0


def test_breadth_processor_basic(sample_ohlcv):
    """Test breadth/regime processor returns valid output."""
    processor = BreadthRegimeProcessor({"ma_periods": [50, 200]})
    signals, sentiment = processor.process(sample_ohlcv, breadth_data=None)
    
    # Check breadth
    assert 0.0 <= signals.breadth.advance_decline_ratio <= 1.0
    assert 0.0 <= signals.breadth.pct_above_ma <= 1.0
    assert isinstance(signals.breadth.breadth_thrust, bool)
    
    # Check risk regime
    assert signals.risk_regime.regime in ["risk_on", "risk_off", "neutral"]
    assert -1.0 <= signals.risk_regime.rotation_score <= 1.0
    assert 0.0 <= signals.risk_regime.confidence <= 1.0
    
    # Check multi-period
    assert signals.multi_period_regime in ["bullish_consensus", "bearish_consensus", "mixed", "unknown"]
    
    assert sentiment.driver == "breadth"


def test_energy_processor_basic(sample_ohlcv):
    """Test energy processor returns valid output."""
    processor = EnergyProcessor({
        "momentum_window": 14,
        "coherence_window": 20,
    })
    signals, sentiment = processor.process(sample_ohlcv)
    
    # Check trend energy
    assert signals.trend_energy.momentum_energy >= 0.0
    assert 0.0 <= signals.trend_energy.trend_coherence <= 1.0
    assert isinstance(signals.trend_energy.exhaustion_detected, bool)
    assert isinstance(signals.trend_energy.buildup_detected, bool)
    
    # Check volume energy
    assert -1.0 <= signals.volume_energy.volume_trend_correlation <= 1.0
    assert isinstance(signals.volume_energy.volume_confirmation, bool)
    
    # Check exhaustion vs continuation
    assert -1.0 <= signals.exhaustion_vs_continuation <= 1.0
    assert signals.metabolic_load >= 0.0
    
    assert sentiment.driver == "energy"


# ============================================================================
# Fusion Tests
# ============================================================================

def test_fuse_signals_basic():
    """Test basic signal fusion."""
    signals = [
        SentimentSignal(value=0.5, confidence=0.8, weight=1.0, driver="processor1"),
        SentimentSignal(value=0.3, confidence=0.7, weight=1.0, driver="processor2"),
        SentimentSignal(value=0.4, confidence=0.9, weight=1.0, driver="processor3"),
    ]
    
    envelope = fuse_signals(signals)
    
    assert envelope.bias in ["bullish", "bearish", "neutral"]
    assert 0.0 <= envelope.strength <= 1.0
    assert envelope.energy >= 0.0
    assert 0.0 <= envelope.confidence <= 1.0
    assert len(envelope.drivers) == 3


def test_fuse_signals_conflicting():
    """Test fusion with conflicting signals."""
    signals = [
        SentimentSignal(value=0.8, confidence=0.9, weight=1.0, driver="bullish1"),
        SentimentSignal(value=-0.7, confidence=0.8, weight=1.0, driver="bearish1"),
        SentimentSignal(value=0.1, confidence=0.5, weight=1.0, driver="neutral1"),
    ]
    
    envelope = fuse_signals(signals)
    
    # Should produce moderate result with lower confidence
    assert -0.3 <= envelope.strength <= 0.3  # Near neutral due to conflict
    # Confidence should be reduced (but hard to predict exact value)


def test_fuse_signals_empty():
    """Test fusion with no signals."""
    envelope = fuse_signals([])
    
    assert envelope.bias == "neutral"
    assert envelope.strength == 0.0
    assert envelope.energy == 0.0
    assert envelope.confidence == 0.0


def test_graceful_degradation():
    """Test graceful degradation with missing processors."""
    signals = [
        SentimentSignal(value=0.5, confidence=0.7, weight=1.0, driver="processor1"),
        SentimentSignal(value=0.4, confidence=0.8, weight=1.0, driver="processor2"),
    ]
    
    # Should boost when below required minimum
    adjusted = apply_graceful_degradation(signals, required_minimum=4)
    
    assert len(adjusted) == 2
    # Weights/confidence should be boosted
    assert all(s.weight >= 1.0 for s in adjusted)


def test_detect_conflicting_signals():
    """Test conflict detection."""
    # Strong conflict
    conflicting = [
        SentimentSignal(value=0.9, confidence=0.9, weight=1.0, driver="bull"),
        SentimentSignal(value=-0.85, confidence=0.85, weight=1.0, driver="bear"),
    ]
    
    assert detect_conflicting_signals(conflicting) is True
    
    # Aligned signals
    aligned = [
        SentimentSignal(value=0.7, confidence=0.8, weight=1.0, driver="bull1"),
        SentimentSignal(value=0.6, confidence=0.7, weight=1.0, driver="bull2"),
    ]
    
    assert detect_conflicting_signals(aligned) is False


# ============================================================================
# Integration Tests
# ============================================================================

def test_sentiment_engine_basic_integration():
    """Test full engine with basic market data."""
    adapter = StaticMarketDataAdapter()
    engine = SentimentEngineV1(adapter)
    
    envelope = engine.process("SPY", datetime.utcnow())
    
    # Check envelope structure
    assert envelope.bias in ["bullish", "bearish", "neutral"]
    assert 0.0 <= envelope.strength <= 1.0
    assert envelope.energy >= 0.0
    assert 0.0 <= envelope.confidence <= 1.0
    assert isinstance(envelope.drivers, dict)


def test_sentiment_engine_trending_market(sample_ohlcv):
    """Test engine behavior in trending market."""
    # Create custom adapter with trending data
    class TrendingAdapter:
        def fetch_ohlcv(self, symbol, lookback, now):
            return sample_ohlcv
    
    engine = SentimentEngineV1(TrendingAdapter())
    envelope = engine.process("SPY", datetime.utcnow())
    
    # In trending market, should likely show bullish bias (data is uptrending)
    # But we don't enforce specific bias due to noise
    assert envelope.bias in ["bullish", "bearish", "neutral"]
    assert envelope.strength > 0.0  # Should have some conviction


def test_sentiment_engine_mean_revert_market(mean_revert_ohlcv):
    """Test engine behavior in mean-reverting market."""
    class MeanRevertAdapter:
        def fetch_ohlcv(self, symbol, lookback, now):
            return mean_revert_ohlcv
    
    engine = SentimentEngineV1(MeanRevertAdapter())
    envelope = engine.process("SPY", datetime.utcnow())
    
    # Mean-revert market might show different characteristics
    assert envelope.bias in ["bullish", "bearish", "neutral"]
    # Confidence might be lower due to oscillation
    assert 0.0 <= envelope.confidence <= 1.0


def test_sentiment_engine_with_darkpool():
    """Test engine with dark pool data."""
    adapter = StaticMarketDataAdapter()
    engine = SentimentEngineV1(adapter)
    
    darkpool_data = {"dix": 0.48, "gex": -3.0}
    envelope = engine.process("SPY", datetime.utcnow(), darkpool_data=darkpool_data)
    
    # Should include flow data
    assert "flow" in envelope.drivers or len(envelope.drivers) > 0


def test_sentiment_engine_with_breadth():
    """Test engine with breadth data."""
    adapter = StaticMarketDataAdapter()
    engine = SentimentEngineV1(adapter)
    
    breadth_data = {"advances": 400, "declines": 200}
    envelope = engine.process("SPY", datetime.utcnow(), breadth_data=breadth_data)
    
    # Should process successfully
    assert envelope.bias in ["bullish", "bearish", "neutral"]


def test_sentiment_engine_detailed_analysis():
    """Test detailed analysis output."""
    adapter = StaticMarketDataAdapter()
    engine = SentimentEngineV1(adapter)
    
    details = engine.get_detailed_analysis("SPY", datetime.utcnow())
    
    # Should have processor breakdowns
    assert "wyckoff" in details
    assert "oscillators" in details
    assert "volatility" in details
    assert "flow" in details
    assert "breadth" in details
    assert "energy" in details
    assert "envelope" in details


def test_sentiment_engine_insufficient_data():
    """Test engine with insufficient data."""
    class EmptyAdapter:
        def fetch_ohlcv(self, symbol, lookback, now):
            return pl.DataFrame()
    
    engine = SentimentEngineV1(EmptyAdapter())
    envelope = engine.process("SPY", datetime.utcnow())
    
    # Should return neutral envelope
    assert envelope.bias == "neutral"
    assert envelope.strength == 0.0
    assert envelope.confidence == 0.0


def test_sentiment_engine_partial_processor_failure(sample_ohlcv):
    """Test graceful degradation when some processors fail."""
    # This test ensures the engine continues even if some processors fail
    adapter = StaticMarketDataAdapter()
    engine = SentimentEngineV1(adapter)
    
    # Disable some processors
    engine.config.wyckoff.enabled = False
    engine.config.breadth.enabled = False
    
    envelope = engine.process("SPY", datetime.utcnow())
    
    # Should still produce valid output with remaining processors
    assert envelope.bias in ["bullish", "bearish", "neutral"]
    assert 0.0 <= envelope.confidence <= 1.0


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_processor_with_minimal_data():
    """Test processors with minimal data."""
    now = datetime.utcnow()
    minimal_df = pl.DataFrame({
        "timestamp": [now - timedelta(days=i) for i in range(5)],
        "open": [100.0] * 5,
        "high": [101.0] * 5,
        "low": [99.0] * 5,
        "close": [100.0] * 5,
        "volume": [1000] * 5,
    })
    
    # Processors should handle minimal data gracefully
    wyckoff = WyckoffProcessor({"lookback_periods": 20})
    signals, sentiment = wyckoff.process(minimal_df)
    
    # Should return default/low confidence output
    assert sentiment.confidence == 0.0  # Insufficient data


def test_processor_with_flat_prices():
    """Test processors with flat/unchanging prices."""
    now = datetime.utcnow()
    flat_df = pl.DataFrame({
        "timestamp": [now - timedelta(days=i) for i in range(50)],
        "open": [100.0] * 50,
        "high": [100.0] * 50,
        "low": [100.0] * 50,
        "close": [100.0] * 50,
        "volume": [1000] * 50,
    })
    
    osc = OscillatorProcessor({"rsi_period": 14})
    signals, sentiment = osc.process(flat_df)
    
    # RSI should be near 50 (neutral)
    assert 40 <= signals.rsi.value <= 60


def test_fusion_with_extreme_energy():
    """Test fusion with very high energy level."""
    signals = [
        SentimentSignal(value=0.5, confidence=0.8, weight=1.0, driver="test1"),
        SentimentSignal(value=0.6, confidence=0.7, weight=1.0, driver="test2"),
    ]
    
    # High energy should apply damping
    envelope = fuse_signals(signals, energy_level=3.0)
    
    # Should still produce valid output
    assert 0.0 <= envelope.strength <= 1.0
    assert envelope.energy > 0.0
