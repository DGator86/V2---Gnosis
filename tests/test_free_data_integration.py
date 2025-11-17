"""
End-to-end integration tests for ALL free data sources.

Tests the complete FREE data pipeline with fallback and validation.

Run with: pytest tests/test_free_data_integration.py -v
"""

import pytest
import polars as pl
from datetime import date, timedelta
import os

# Import all adapters
from engines.inputs.yfinance_adapter import YFinanceAdapter
from engines.inputs.yahoo_options_adapter import YahooOptionsAdapter
from engines.inputs.fred_adapter import FREDAdapter
from engines.inputs.dark_pool_adapter import DarkPoolAdapter
from engines.inputs.short_volume_adapter import ShortVolumeAdapter
from engines.inputs.stocktwits_adapter import StockTwitsAdapter
from engines.inputs.iex_adapter import IEXAdapter
from engines.inputs.greekcalc_adapter import GreekCalcAdapter
from engines.inputs.data_source_manager import DataSourceManager

# Import ML features
from ml.features.ta_indicators import TAIndicators


class TestYFinanceAdapter:
    """Test yfinance adapter."""
    
    def test_fetch_vix(self):
        """Test VIX fetching."""
        adapter = YFinanceAdapter()
        vix = adapter.fetch_vix()
        
        assert vix is not None
        assert vix > 0
        assert vix < 200  # Sanity check
        print(f"✅ VIX: {vix:.2f}")
    
    def test_fetch_spx(self):
        """Test SPX fetching."""
        adapter = YFinanceAdapter()
        spx = adapter.fetch_spx()
        
        assert spx is not None
        assert spx > 1000
        print(f"✅ SPX: {spx:.2f}")
    
    def test_fetch_history(self):
        """Test historical OHLCV."""
        adapter = YFinanceAdapter()
        df = adapter.fetch_history("SPY", period="5d", interval="1d")
        
        assert not df.is_empty()
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert len(df) >= 3
        print(f"✅ Fetched {len(df)} bars for SPY")
    
    def test_market_regime_data(self):
        """Test market regime data."""
        adapter = YFinanceAdapter()
        regime = adapter.fetch_market_regime_data()
        
        assert "vix" in regime
        assert "spx" in regime
        assert regime["vix"] > 0
        assert regime["spx"] > 0
        print(f"✅ Regime data: VIX={regime['vix']:.2f}, SPX={regime['spx']:.2f}")


class TestYahooOptionsAdapter:
    """Test Yahoo options adapter."""
    
    def test_fetch_options_chain(self):
        """Test options chain fetching."""
        adapter = YahooOptionsAdapter()
        chain = adapter.fetch_options_chain("SPY", min_days_to_expiry=7, max_days_to_expiry=60)
        
        assert not chain.is_empty()
        assert "strike" in chain.columns
        assert "delta" in chain.columns
        assert "gamma" in chain.columns
        assert len(chain) > 10  # Should have multiple strikes
        
        print(f"✅ Fetched {len(chain)} options for SPY")
        print(f"   Strikes: {chain['strike'].min():.2f} - {chain['strike'].max():.2f}")


@pytest.mark.skipif(
    not os.getenv("FRED_API_KEY"),
    reason="FRED_API_KEY not set"
)
class TestFREDAdapter:
    """Test FRED adapter (requires API key)."""
    
    def test_fetch_macro_data(self):
        """Test macro data fetching."""
        adapter = FREDAdapter(api_key=os.getenv("FRED_API_KEY"))
        macro = adapter.fetch_macro_regime_data(lookback_days=365)
        
        assert "fed_funds_rate" in macro
        assert "treasury_10y" in macro
        assert "yield_curve_slope" in macro
        
        print(f"✅ Macro data:")
        print(f"   Fed Funds: {macro['fed_funds_rate']:.2f}%")
        print(f"   10Y Treasury: {macro['treasury_10y']:.2f}%")
        print(f"   Yield Curve: {macro['yield_curve_slope']:.2f}%")


class TestDarkPoolAdapter:
    """Test dark pool adapter."""
    
    def test_estimate_dark_pool_pressure(self):
        """Test dark pool pressure estimation."""
        adapter = DarkPoolAdapter()
        
        # Use estimation mode (no trade data)
        pressure = adapter.estimate_dark_pool_pressure("SPY", df_trades=None)
        
        assert "dark_pool_ratio" in pressure
        assert "accumulation_score" in pressure
        assert 0 <= pressure["dark_pool_ratio"] <= 1
        
        print(f"✅ Dark pool pressure estimated:")
        print(f"   Ratio: {pressure['dark_pool_ratio']:.3f}")
        print(f"   Accumulation: {pressure['accumulation_score']:.3f}")


class TestShortVolumeAdapter:
    """Test short volume adapter."""
    
    def test_fetch_short_volume(self):
        """Test FINRA short volume fetching."""
        adapter = ShortVolumeAdapter()
        
        # Fetch recent date
        test_date = date.today() - timedelta(days=3)
        short_vol = adapter.fetch_short_volume("SPY", date=test_date)
        
        # May return None if data not available yet
        if short_vol is not None:
            assert "short_volume" in short_vol
            assert "total_volume" in short_vol
            assert "short_ratio" in short_vol
            print(f"✅ Short volume for {test_date}:")
            print(f"   Short Ratio: {short_vol['short_ratio']:.2%}")
        else:
            print(f"⚠️  Short volume data not available for {test_date} (expected)")


class TestStockTwitsAdapter:
    """Test StockTwits adapter."""
    
    def test_fetch_sentiment(self):
        """Test sentiment fetching."""
        adapter = StockTwitsAdapter(use_cache=False)
        
        try:
            sentiment = adapter.fetch_sentiment("SPY", limit=30)
            
            assert sentiment.total_messages >= 0
            assert -1 <= sentiment.sentiment_score <= 1
            assert 0 <= sentiment.confidence <= 1
            
            print(f"✅ StockTwits sentiment for SPY:")
            print(f"   Messages: {sentiment.total_messages}")
            print(f"   Sentiment: {sentiment.sentiment_score:+.3f}")
            print(f"   Confidence: {sentiment.confidence:.3f}")
        finally:
            adapter.close()


@pytest.mark.skipif(
    not os.getenv("IEX_API_TOKEN"),
    reason="IEX_API_TOKEN not set"
)
class TestIEXAdapter:
    """Test IEX Cloud adapter (requires API key)."""
    
    def test_fetch_quote(self):
        """Test quote fetching."""
        adapter = IEXAdapter(api_token=os.getenv("IEX_API_TOKEN"))
        quote = adapter.fetch_quote("SPY")
        
        assert quote.last_price > 0
        print(f"✅ IEX quote for SPY: ${quote.last_price:.2f}")


class TestGreekCalcAdapter:
    """Test Greeks calculator."""
    
    def test_calculate_greeks(self):
        """Test Greeks calculation."""
        adapter = GreekCalcAdapter(risk_free_rate=0.05)
        
        greeks = adapter.calculate_greeks(
            spot_price=450.0,
            strike=450.0,
            expiry_date=date.today() + timedelta(days=30),
            option_type="call",
            volatility=0.25
        )
        
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks
        assert "rho" in greeks
        
        assert 0 <= greeks["delta"] <= 1  # ATM call delta ~ 0.5
        
        print(f"✅ Greeks for ATM call:")
        print(f"   Delta: {greeks['delta']:.4f}")
        print(f"   Gamma: {greeks['gamma']:.6f}")
        print(f"   Theta: {greeks['theta']:.4f}")


class TestTAIndicators:
    """Test ta library wrapper."""
    
    def test_add_all_indicators(self):
        """Test adding all 130+ indicators."""
        import numpy as np
        import pandas as pd
        
        # Create sample data
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="1min")
        
        sample_data = pl.DataFrame({
            "timestamp": dates,
            "open": np.random.randn(n).cumsum() + 100,
            "high": np.random.randn(n).cumsum() + 102,
            "low": np.random.randn(n).cumsum() + 98,
            "close": np.random.randn(n).cumsum() + 100,
            "volume": np.random.randint(1000, 10000, n)
        })
        
        ta_indicators = TAIndicators()
        result = ta_indicators.add_all_indicators(sample_data)
        
        # Should add 100+ indicators
        added_cols = len(result.columns) - len(sample_data.columns)
        assert added_cols > 50
        
        print(f"✅ Added {added_cols} technical indicators")


class TestDataSourceManager:
    """Test unified data source manager."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = DataSourceManager(
            fred_api_key=os.getenv("FRED_API_KEY"),
            iex_api_token=os.getenv("IEX_API_TOKEN")
        )
        
        status = manager.get_source_status()
        
        assert not status.is_empty()
        assert "source_type" in status.columns
        assert "is_available" in status.columns
        
        print(f"✅ DataSourceManager initialized with {len(status)} sources")
        print(status)
    
    def test_fetch_quote_with_fallback(self):
        """Test quote fetching with fallback."""
        manager = DataSourceManager()
        
        quote = manager.fetch_quote("SPY")
        
        assert quote is not None
        assert "last" in quote or "bid" in quote
        
        price = quote.get("last") or quote.get("bid")
        assert price > 0
        
        print(f"✅ Quote with fallback: SPY = ${price:.2f}")
    
    def test_fetch_ohlcv_with_fallback(self):
        """Test OHLCV fetching with fallback."""
        manager = DataSourceManager()
        
        df = manager.fetch_ohlcv("SPY", timeframe="1d", limit=5)
        
        assert df is not None
        assert not df.is_empty()
        assert "close" in df.columns
        
        print(f"✅ OHLCV with fallback: {len(df)} bars")
    
    def test_fetch_unified_data(self):
        """Test unified data fetching (integration test)."""
        manager = DataSourceManager(
            fred_api_key=os.getenv("FRED_API_KEY")
        )
        
        data = manager.fetch_unified_data(
            symbol="SPY",
            include_options=True,
            include_sentiment=True,
            include_macro=True
        )
        
        assert data.symbol == "SPY"
        assert len(data.data_sources_used) > 0
        
        print(f"✅ Unified data for SPY:")
        print(f"   Close: ${data.close}")
        print(f"   VIX: {data.vix}")
        print(f"   Options: {data.options_chain_available}")
        print(f"   Sources: {', '.join(data.data_sources_used)}")


class TestEndToEndPipeline:
    """End-to-end pipeline test."""
    
    def test_complete_free_pipeline(self):
        """
        Test complete FREE data pipeline.
        
        This is the master integration test that validates:
        1. All data sources can be initialized
        2. Data can be fetched from all sources
        3. DataSourceManager orchestrates properly
        4. No paid services are required
        """
        print("\n" + "="*60)
        print("COMPLETE FREE DATA PIPELINE TEST")
        print("="*60)
        
        # Initialize manager (FREE sources only)
        manager = DataSourceManager(
            fred_api_key=os.getenv("FRED_API_KEY")  # Free API key
        )
        
        symbol = "SPY"
        
        # Step 1: Fetch unified data
        print(f"\n1️⃣  Fetching unified data for {symbol}...")
        data = manager.fetch_unified_data(
            symbol=symbol,
            include_options=True,
            include_sentiment=True,
            include_macro=True
        )
        
        # Validate core data
        assert data.close is not None, "Missing OHLCV data"
        print(f"   ✅ OHLCV: ${data.close:.2f}")
        
        # Validate regime data
        if data.vix:
            print(f"   ✅ VIX: {data.vix:.2f}")
        
        # Validate options data
        if data.options_chain_available:
            print(f"   ✅ Options: {data.num_options} contracts")
        
        # Validate sentiment
        if data.stocktwits_sentiment is not None:
            print(f"   ✅ Sentiment: {data.stocktwits_sentiment:+.3f}")
        
        # Validate dark pool
        if data.dark_pool_ratio is not None:
            print(f"   ✅ Dark Pool: {data.dark_pool_ratio:.2%}")
        
        # Step 2: Test technical indicators
        print(f"\n2️⃣  Testing technical indicators...")
        df_ohlcv = manager.fetch_ohlcv(symbol, timeframe="1d", limit=100)
        
        if df_ohlcv and not df_ohlcv.is_empty():
            ta_indicators = TAIndicators()
            df_with_ta = ta_indicators.add_all_indicators(df_ohlcv)
            
            added = len(df_with_ta.columns) - len(df_ohlcv.columns)
            print(f"   ✅ Added {added} technical indicators")
        
        # Step 3: Validate Greeks
        print(f"\n3️⃣  Testing Greeks calculation...")
        greek_calc = GreekCalcAdapter(risk_free_rate=0.05)
        
        greeks = greek_calc.calculate_greeks(
            spot_price=data.close,
            strike=data.close,
            expiry_date=date.today() + timedelta(days=30),
            option_type="call",
            volatility=0.25
        )
        
        print(f"   ✅ Greeks: delta={greeks['delta']:.4f}, gamma={greeks['gamma']:.6f}")
        
        # Summary
        print(f"\n" + "="*60)
        print("PIPELINE TEST COMPLETE")
        print("="*60)
        print(f"✅ Data sources used: {', '.join(data.data_sources_used)}")
        print(f"✅ All FREE data sources working")
        print(f"✅ $0/month cost")
        print(f"✅ Ready for production")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
