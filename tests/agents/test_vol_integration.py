# tests/agents/test_vol_integration.py

"""
Tests for volatility intelligence integration with Trade Agent v2.5.

Tests cover:
- VolatilityIntelligence class functionality
- Context enhancement with vol signals
- Strategy preference scoring
- Surface caching
"""

from datetime import date, datetime, timedelta

import pytest

from agents.trade_agent.schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    VolatilityRegime,
    Timeframe,
)
from agents.trade_agent.vol_surface import (
    IVDataPoint,
    VolSurface,
    load_vol_surface,
)
from agents.trade_agent.vol_integration import (
    VolatilityIntelligence,
    create_vol_intelligence_layer,
)


@pytest.fixture
def sample_context():
    """Create a sample ComposerTradeContext."""
    return ComposerTradeContext(
        asset="SPY",
        direction=Direction.BULLISH,
        confidence=0.7,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=0.5,
        gamma_exposure=1000.0,
        vanna_exposure=500.0,
        charm_exposure=200.0,
        liquidity_score=0.9,
    )


@pytest.fixture
def low_iv_surface():
    """Create a surface with low IV (expansion scenario)."""
    today = date.today()
    expiry_30d = today + timedelta(days=30)
    
    data = [
        IVDataPoint(strike=100.0, expiry=expiry_30d, iv=0.15, option_type="call"),
        IVDataPoint(strike=100.0, expiry=expiry_30d, iv=0.16, option_type="put"),
    ]
    
    # Historical IVs showing current is at low end
    historical = [0.20, 0.22, 0.25, 0.18, 0.23, 0.21] * 42  # 252 days
    
    return load_vol_surface(
        symbol="SPY",
        as_of_date=datetime.now(),
        iv_data=data,
        historical_ivs=historical,
    )


@pytest.fixture
def high_iv_surface():
    """Create a surface with high IV (crush scenario)."""
    today = date.today()
    expiry_30d = today + timedelta(days=30)
    
    data = [
        IVDataPoint(strike=100.0, expiry=expiry_30d, iv=0.45, option_type="call"),
        IVDataPoint(strike=100.0, expiry=expiry_30d, iv=0.47, option_type="put"),
    ]
    
    # Historical IVs showing current is at high end
    historical = [0.20, 0.22, 0.25, 0.18, 0.23, 0.21] * 42  # 252 days
    
    return load_vol_surface(
        symbol="SPY",
        as_of_date=datetime.now(),
        iv_data=data,
        historical_ivs=historical,
    )


@pytest.fixture
def rich_wings_surface():
    """Create a surface with rich wings (favorable for condors/butterflies)."""
    today = date.today()
    expiry_30d = today + timedelta(days=30)
    
    data = []
    
    # Create smile with rich wings
    for strike in [90, 95, 100, 105, 110]:
        iv = 0.25 if strike == 100 else 0.35  # Wings have higher IV
        data.append(IVDataPoint(strike=float(strike), expiry=expiry_30d, iv=iv, option_type="call"))
    
    historical = [0.25] * 252
    
    return load_vol_surface(
        symbol="SPY",
        as_of_date=datetime.now(),
        iv_data=data,
        historical_ivs=historical,
    )


class TestVolatilityIntelligence:
    """Test VolatilityIntelligence class."""
    
    def test_initialization(self):
        """Test VolatilityIntelligence initialization."""
        vol_intel = VolatilityIntelligence(default_lookback_days=252)
        
        assert vol_intel.default_lookback_days == 252
        assert len(vol_intel._surface_cache) == 0
    
    def test_analyze_surface(self, low_iv_surface):
        """Test complete surface analysis."""
        vol_intel = VolatilityIntelligence()
        
        iv_rank, skew_metrics, vol_signals = vol_intel.analyze_surface(low_iv_surface)
        
        # Verify all components returned
        assert iv_rank is not None
        assert skew_metrics is not None
        assert vol_signals is not None
        
        # Low IV should indicate expansion
        assert vol_signals.expansion_probability > 0.5
    
    def test_enhance_context_no_surface(self, sample_context):
        """Test context enhancement with no surface data."""
        vol_intel = VolatilityIntelligence()
        
        enhanced_ctx, signals = vol_intel.enhance_context_with_vol_intel(sample_context, surface=None)
        
        # Should return original context unchanged
        assert enhanced_ctx.asset == sample_context.asset
        assert enhanced_ctx.volatility_regime == sample_context.volatility_regime
        assert signals is None
    
    def test_enhance_context_with_surface(self, sample_context, low_iv_surface):
        """Test context enhancement with surface data."""
        vol_intel = VolatilityIntelligence()
        
        enhanced_ctx, signals = vol_intel.enhance_context_with_vol_intel(sample_context, surface=low_iv_surface)
        
        assert enhanced_ctx is not None
        assert signals is not None
        
        # Low IV should trigger expansion regime
        assert enhanced_ctx.volatility_regime in [VolatilityRegime.LOW, VolatilityRegime.VOL_EXPANSION]
    
    def test_map_signals_to_regime_expansion(self, sample_context, low_iv_surface):
        """Test regime mapping for expansion scenario."""
        vol_intel = VolatilityIntelligence()
        
        iv_rank, skew_metrics, vol_signals = vol_intel.analyze_surface(low_iv_surface)
        
        # High expansion probability should map to VOL_EXPANSION
        vol_signals.expansion_probability = 0.8
        
        regime = vol_intel._map_signals_to_regime(vol_signals, sample_context.volatility_regime)
        
        assert regime == VolatilityRegime.VOL_EXPANSION
    
    def test_map_signals_to_regime_crush(self, sample_context, high_iv_surface):
        """Test regime mapping for crush scenario."""
        vol_intel = VolatilityIntelligence()
        
        iv_rank, skew_metrics, vol_signals = vol_intel.analyze_surface(high_iv_surface)
        
        # High crush risk should map to VOL_CRUSH
        vol_signals.crush_risk = 0.8
        
        regime = vol_intel._map_signals_to_regime(vol_signals, sample_context.volatility_regime)
        
        assert regime == VolatilityRegime.VOL_CRUSH
    
    def test_get_strategy_preferences_expansion(self, low_iv_surface):
        """Test strategy preferences for expansion scenario."""
        vol_intel = VolatilityIntelligence()
        
        _, _, vol_signals = vol_intel.analyze_surface(low_iv_surface)
        
        # Force expansion scenario
        vol_signals.expansion_probability = 0.8
        
        preferences = vol_intel.get_strategy_preferences(vol_signals)
        
        # Straddles/strangles should be highly preferred
        assert preferences.get("straddle", 0) > 0.7
        assert preferences.get("strangle", 0) > 0.7
    
    def test_get_strategy_preferences_crush(self, high_iv_surface):
        """Test strategy preferences for crush scenario."""
        vol_intel = VolatilityIntelligence()
        
        _, _, vol_signals = vol_intel.analyze_surface(high_iv_surface)
        
        # Force crush scenario
        vol_signals.crush_risk = 0.8
        vol_signals.expansion_probability = 0.1
        
        preferences = vol_intel.get_strategy_preferences(vol_signals)
        
        # Straddles/strangles should be disfavored
        assert preferences.get("straddle", 1.0) < 0.4
        assert preferences.get("strangle", 1.0) < 0.4
    
    def test_get_strategy_preferences_rich_wings(self, rich_wings_surface):
        """Test strategy preferences with rich wings."""
        vol_intel = VolatilityIntelligence()
        
        _, _, vol_signals = vol_intel.analyze_surface(rich_wings_surface)
        
        # Force rich wings
        vol_signals.rich_wings = True
        
        preferences = vol_intel.get_strategy_preferences(vol_signals)
        
        # Condors and butterflies should be highly preferred
        assert preferences.get("iron_condor", 0) > 0.7
        assert preferences.get("broken_wing_butterfly", 0) > 0.7
    
    def test_get_strategy_preferences_calendars(self, low_iv_surface):
        """Test strategy preferences for calendar spreads."""
        vol_intel = VolatilityIntelligence()
        
        _, _, vol_signals = vol_intel.analyze_surface(low_iv_surface)
        
        # Force calendar-favorable conditions
        vol_signals.skew_favorable_for_calendars = True
        
        preferences = vol_intel.get_strategy_preferences(vol_signals)
        
        # Calendars should be highly preferred
        assert preferences.get("calendar_spread", 0) > 0.7
        assert preferences.get("diagonal_spread", 0) > 0.6
    
    def test_cache_surface(self, low_iv_surface):
        """Test surface caching."""
        vol_intel = VolatilityIntelligence()
        
        vol_intel.cache_surface("SPY", low_iv_surface)
        
        cached = vol_intel.get_cached_surface("SPY")
        
        assert cached is not None
        assert cached.symbol == "SPY"
    
    def test_get_cached_surface_miss(self):
        """Test cache miss."""
        vol_intel = VolatilityIntelligence()
        
        cached = vol_intel.get_cached_surface("AAPL")
        
        assert cached is None
    
    def test_clear_cache(self, low_iv_surface):
        """Test cache clearing."""
        vol_intel = VolatilityIntelligence()
        
        vol_intel.cache_surface("SPY", low_iv_surface)
        vol_intel.clear_cache()
        
        cached = vol_intel.get_cached_surface("SPY")
        
        assert cached is None


class TestFactoryFunction:
    """Test factory function for creating VolatilityIntelligence."""
    
    def test_create_vol_intelligence_layer(self):
        """Test factory function."""
        vol_intel = create_vol_intelligence_layer(lookback_days=252)
        
        assert isinstance(vol_intel, VolatilityIntelligence)
        assert vol_intel.default_lookback_days == 252
    
    def test_create_vol_intelligence_layer_custom_lookback(self):
        """Test factory with custom lookback."""
        vol_intel = create_vol_intelligence_layer(lookback_days=126)
        
        assert vol_intel.default_lookback_days == 126


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_end_to_end_context_enhancement(self, sample_context, low_iv_surface):
        """Test complete workflow from context to enhanced context."""
        vol_intel = create_vol_intelligence_layer()
        
        # Cache surface
        vol_intel.cache_surface("SPY", low_iv_surface)
        
        # Enhance context
        enhanced_ctx, signals = vol_intel.enhance_context_with_vol_intel(
            sample_context,
            surface=vol_intel.get_cached_surface("SPY")
        )
        
        assert enhanced_ctx is not None
        assert signals is not None
        
        # Get strategy preferences
        preferences = vol_intel.get_strategy_preferences(signals)
        
        assert len(preferences) > 0
        assert all(0.0 <= score <= 1.0 for score in preferences.values())
    
    def test_multiple_symbols_caching(self, low_iv_surface, high_iv_surface):
        """Test caching multiple symbols."""
        vol_intel = create_vol_intelligence_layer()
        
        # Update high_iv_surface symbol to differentiate
        high_iv_surface.symbol = "QQQ"
        
        vol_intel.cache_surface("SPY", low_iv_surface)
        vol_intel.cache_surface("QQQ", high_iv_surface)
        
        spy_cached = vol_intel.get_cached_surface("SPY")
        qqq_cached = vol_intel.get_cached_surface("QQQ")
        
        assert spy_cached.symbol == "SPY"
        assert qqq_cached.symbol == "QQQ"
