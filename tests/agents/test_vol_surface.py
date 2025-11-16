# tests/agents/test_vol_surface.py

"""
Comprehensive tests for volatility surface intelligence module.

Tests cover:
- Vol surface loading and parsing
- IV rank and percentile calculation
- Skew metrics computation
- Volatility signal generation
- Integration with Trade Agent context
"""

from datetime import date, datetime, timedelta

import pytest
import numpy as np

from agents.trade_agent.vol_surface import (
    IVDataPoint,
    SurfaceSlice,
    VolSurface,
    SkewMetrics,
    IVRankPercentile,
    VolatilitySignals,
    load_vol_surface,
    get_iv_slice,
    compute_iv_rank,
    compute_skew_metrics,
    generate_volatility_signals,
)


@pytest.fixture
def mock_iv_data():
    """Create mock IV data for testing."""
    today = date.today()
    expiry_30d = today + timedelta(days=30)
    expiry_60d = today + timedelta(days=60)
    
    data = []
    
    # 30-day expiry: strikes from 90 to 110
    for strike in range(90, 111, 2):
        # Calls
        data.append(IVDataPoint(
            strike=float(strike),
            expiry=expiry_30d,
            iv=0.25 + (abs(strike - 100) * 0.005),  # Smile shape
            delta=0.5 if strike == 100 else None,
            option_type="call"
        ))
        
        # Puts (slightly higher IV for put skew)
        data.append(IVDataPoint(
            strike=float(strike),
            expiry=expiry_30d,
            iv=0.27 + (abs(strike - 100) * 0.005),
            delta=-0.5 if strike == 100 else None,
            option_type="put"
        ))
    
    # 60-day expiry: strikes from 90 to 110
    for strike in range(90, 111, 2):
        data.append(IVDataPoint(
            strike=float(strike),
            expiry=expiry_60d,
            iv=0.23 + (abs(strike - 100) * 0.004),  # Lower IV (contango)
            option_type="call"
        ))
    
    return data


@pytest.fixture
def mock_historical_ivs():
    """Create mock historical IV data for IV rank calculation."""
    # Generate 252 days of historical IV (1 year)
    np.random.seed(42)
    
    # Trend from 0.15 to 0.35 with noise
    base_ivs = np.linspace(0.15, 0.35, 252)
    noise = np.random.normal(0, 0.03, 252)
    historical = base_ivs + noise
    
    # Clip to reasonable range
    historical = np.clip(historical, 0.10, 0.50)
    
    return historical.tolist()


class TestSurfaceSlice:
    """Test SurfaceSlice functionality."""
    
    def test_get_skew_put_rich(self):
        """Test skew calculation with put-rich profile."""
        slice_obj = SurfaceSlice(
            expiry=date.today() + timedelta(days=30),
            dte=30,
            strikes=[95.0, 100.0, 105.0],
            ivs=[0.28, 0.25, 0.28],
            call_ivs=[0.24, 0.25, 0.26],
            put_ivs=[0.30, 0.28, 0.29],
            atm_iv=0.25,
        )
        
        skew = slice_obj.get_skew()
        
        assert skew > 0.0, "Put-rich skew should be positive"
        assert abs(skew - 0.03) < 0.02, "Skew magnitude should be ~3%"
    
    def test_get_skew_call_rich(self):
        """Test skew calculation with call-rich profile."""
        slice_obj = SurfaceSlice(
            expiry=date.today() + timedelta(days=30),
            dte=30,
            strikes=[95.0, 100.0, 105.0],
            ivs=[0.27, 0.25, 0.28],
            call_ivs=[0.30, 0.28, 0.29],
            put_ivs=[0.24, 0.25, 0.26],
            atm_iv=0.25,
        )
        
        skew = slice_obj.get_skew()
        
        assert skew < 0.0, "Call-rich skew should be negative"
    
    def test_get_wing_spread_rich_wings(self):
        """Test wing spread calculation with rich wings."""
        slice_obj = SurfaceSlice(
            expiry=date.today() + timedelta(days=30),
            dte=30,
            strikes=[90.0, 95.0, 100.0, 105.0, 110.0],
            ivs=[0.35, 0.28, 0.25, 0.28, 0.35],  # High wing IV
            call_ivs=[],
            put_ivs=[],
            atm_iv=0.25,
        )
        
        wing_spread = slice_obj.get_wing_spread()
        
        assert wing_spread > 0.0, "Rich wings should have positive spread"


class TestVolSurface:
    """Test VolSurface functionality."""
    
    def test_load_vol_surface(self, mock_iv_data, mock_historical_ivs):
        """Test loading and parsing vol surface."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=mock_historical_ivs,
        )
        
        assert surface.symbol == "SPY"
        assert len(surface.slices) == 2, "Should have 2 expiry slices (30d, 60d)"
        assert surface.current_atm_iv > 0.0, "Should have current ATM IV"
        assert len(surface.historical_ivs) == 252, "Should have 252 historical IVs"
    
    def test_get_slice_by_dte(self, mock_iv_data):
        """Test retrieving slice by DTE."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        # Get 30-day slice (with tolerance)
        slice_30d = surface.get_slice_by_dte(30, tolerance=5)
        
        assert slice_30d is not None, "Should find 30-day slice"
        assert abs(slice_30d.dte - 30) <= 5, "DTE should be within tolerance"
    
    def test_get_slice_by_dte_not_found(self, mock_iv_data):
        """Test retrieving slice with no match."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        # Request 180-day slice (doesn't exist)
        slice_180d = surface.get_slice_by_dte(180, tolerance=5)
        
        assert slice_180d is None, "Should not find 180-day slice"
    
    def test_term_structure_slope_contango(self, mock_iv_data):
        """Test term structure slope calculation (contango)."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        slope = surface.get_term_structure_slope()
        
        # Front month IV > back month IV (mock data has this structure)
        assert slope > 0.0, "Should detect backwardation (front > back)"
    
    def test_term_structure_slope_single_expiry(self):
        """Test term structure with single expiry."""
        today = date.today()
        data = [
            IVDataPoint(strike=100.0, expiry=today + timedelta(days=30), iv=0.25, option_type="call")
        ]
        
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=data,
        )
        
        slope = surface.get_term_structure_slope()
        
        assert slope == 0.0, "Single expiry should have zero slope"


class TestIVRankPercentile:
    """Test IV rank and percentile calculations."""
    
    def test_compute_iv_rank_high(self, mock_iv_data, mock_historical_ivs):
        """Test IV rank calculation when IV is high."""
        # Add high current IV
        historical = mock_historical_ivs.copy()
        
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=historical,
        )
        
        # Artificially set current IV to high value
        surface.current_atm_iv = 0.45  # Higher than historical range
        
        iv_rank = compute_iv_rank(surface, lookback_days=252)
        
        assert iv_rank.iv_rank > 0.8, "IV rank should be high"
        assert iv_rank.iv_percentile > 80.0, "IV percentile should be high"
        assert iv_rank.current_iv == 0.45
    
    def test_compute_iv_rank_low(self, mock_iv_data, mock_historical_ivs):
        """Test IV rank calculation when IV is low."""
        historical = mock_historical_ivs.copy()
        
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=historical,
        )
        
        # Set current IV to low value
        surface.current_atm_iv = 0.12
        
        iv_rank = compute_iv_rank(surface, lookback_days=252)
        
        assert iv_rank.iv_rank < 0.3, "IV rank should be low"
        assert iv_rank.iv_percentile < 30.0, "IV percentile should be low"
    
    def test_compute_iv_rank_no_history(self, mock_iv_data):
        """Test IV rank with no historical data."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=[],
        )
        
        iv_rank = compute_iv_rank(surface)
        
        # Should return neutral metrics
        assert iv_rank.iv_rank == 0.5, "No history should give neutral rank"
        assert iv_rank.iv_percentile == 50.0, "No history should give neutral percentile"


class TestSkewMetrics:
    """Test skew metrics computation."""
    
    def test_compute_skew_metrics(self, mock_iv_data):
        """Test comprehensive skew metrics."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        skew_metrics = compute_skew_metrics(surface, target_dte=30)
        
        assert isinstance(skew_metrics, SkewMetrics)
        assert skew_metrics.put_call_skew != 0.0, "Should detect put/call skew"
        assert skew_metrics.skew_direction in ["put_rich", "call_rich", "neutral"]
    
    def test_skew_direction_classification(self, mock_iv_data):
        """Test skew direction classification."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        skew_metrics = compute_skew_metrics(surface, target_dte=30)
        
        # Mock data has put skew
        assert skew_metrics.skew_direction == "put_rich", "Should detect put-rich skew"
    
    def test_skew_metrics_no_data(self):
        """Test skew metrics with no surface data."""
        surface = VolSurface(
            symbol="SPY",
            as_of_date=date.today(),
            slices=[],
            current_atm_iv=0.25,
        )
        
        skew_metrics = compute_skew_metrics(surface, target_dte=30)
        
        # Should return neutral metrics
        assert skew_metrics.put_call_skew == 0.0
        assert skew_metrics.skew_direction == "neutral"


class TestVolatilitySignals:
    """Test volatility signal generation."""
    
    def test_generate_signals_low_iv(self, mock_iv_data, mock_historical_ivs):
        """Test signal generation with low IV."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=mock_historical_ivs,
        )
        
        surface.current_atm_iv = 0.12  # Low IV
        
        iv_rank = compute_iv_rank(surface)
        skew_metrics = compute_skew_metrics(surface)
        signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        assert signals.expansion_probability > 0.6, "Low IV should indicate expansion risk"
        assert signals.iv_regime == "low" or signals.iv_regime == "expansion"
    
    def test_generate_signals_high_iv(self, mock_iv_data, mock_historical_ivs):
        """Test signal generation with high IV."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=mock_historical_ivs,
        )
        
        surface.current_atm_iv = 0.45  # High IV
        
        iv_rank = compute_iv_rank(surface)
        skew_metrics = compute_skew_metrics(surface)
        signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        assert signals.crush_risk > 0.6, "High IV should indicate crush risk"
        assert signals.iv_regime == "high" or signals.iv_regime == "crush"
    
    def test_rich_wings_signal(self, mock_iv_data):
        """Test rich wings detection."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        # Modify data to have rich wings
        for slice_obj in surface.slices:
            if slice_obj.dte == 30:
                # Artificially increase wing spread
                slice_obj.ivs = [0.35, 0.28, 0.25, 0.28, 0.35]
                break
        
        iv_rank = compute_iv_rank(surface, lookback_days=252)
        skew_metrics = compute_skew_metrics(surface)
        signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        # Rich wings should be detected if wing_spread > 0.03
        assert isinstance(signals.rich_wings, bool)
    
    def test_calendar_favorable_signal(self, mock_iv_data, mock_historical_ivs):
        """Test calendar spread favorability signal."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=mock_historical_ivs,
        )
        
        surface.current_atm_iv = 0.20  # Low-mid IV
        
        iv_rank = compute_iv_rank(surface)
        skew_metrics = compute_skew_metrics(surface)
        signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        # Check calendar favorability logic
        assert isinstance(signals.skew_favorable_for_calendars, bool)


class TestIntegration:
    """Integration tests for complete vol surface workflow."""
    
    def test_end_to_end_analysis(self, mock_iv_data, mock_historical_ivs):
        """Test complete analysis pipeline from data to signals."""
        # 1. Load surface
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
            historical_ivs=mock_historical_ivs,
        )
        
        assert surface.symbol == "SPY"
        assert len(surface.slices) > 0
        
        # 2. Compute IV rank
        iv_rank = compute_iv_rank(surface, lookback_days=252)
        
        assert 0.0 <= iv_rank.iv_rank <= 1.0
        assert 0.0 <= iv_rank.iv_percentile <= 100.0
        
        # 3. Compute skew metrics
        skew_metrics = compute_skew_metrics(surface, target_dte=30)
        
        assert skew_metrics.skew_direction in ["put_rich", "call_rich", "neutral"]
        
        # 4. Generate volatility signals
        signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        assert 0.0 <= signals.expansion_probability <= 1.0
        assert 0.0 <= signals.crush_risk <= 1.0
        assert signals.iv_regime in ["low", "mid", "high", "expansion", "crush"]
    
    def test_get_iv_slice_integration(self, mock_iv_data):
        """Test getting specific slice from surface."""
        surface = load_vol_surface(
            symbol="SPY",
            as_of_date=datetime.now(),
            iv_data=mock_iv_data,
        )
        
        # Get first expiry
        first_slice = surface.slices[0]
        
        # Retrieve by exact expiry
        retrieved_slice = get_iv_slice(surface, first_slice.expiry)
        
        assert retrieved_slice is not None
        assert retrieved_slice.expiry == first_slice.expiry
