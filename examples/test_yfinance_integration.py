"""Test yfinance integration and sample data generation.

This script demonstrates:
1. Fetching VIX and SPX from yfinance (FREE)
2. Generating sample options chain data for testing
3. Running a complete ML training pipeline with free data
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.inputs.yfinance_adapter import YFinanceAdapter, get_market_regime_data
from engines.inputs.sample_options_generator import generate_sample_chain_for_testing
from loguru import logger


def test_yfinance_connection():
    """Test yfinance connection and data fetching."""
    print("\n" + "="*60)
    print("TEST 1: YFINANCE CONNECTION")
    print("="*60)
    
    adapter = YFinanceAdapter()
    
    # Test connection
    print("\n1. Testing connection...")
    if adapter.test_connection():
        print("   ✅ Connection successful")
    else:
        print("   ❌ Connection failed")
        return False
    
    # Fetch VIX
    print("\n2. Fetching VIX...")
    try:
        vix = adapter.fetch_vix()
        print(f"   ✅ VIX: {vix:.2f}")
        
        # Interpret VIX
        if vix < 15:
            regime = "LOW (calm markets)"
        elif vix < 20:
            regime = "NORMAL (typical volatility)"
        elif vix < 30:
            regime = "ELEVATED (heightened uncertainty)"
        else:
            regime = "CRISIS (high fear/panic)"
        
        print(f"   📊 VIX Regime: {regime}")
        
    except Exception as e:
        print(f"   ❌ VIX fetch failed: {e}")
        return False
    
    # Fetch SPX
    print("\n3. Fetching SPX...")
    try:
        spx = adapter.fetch_spx(use_etf=True)
        print(f"   ✅ SPX (via SPY): {spx:.2f}")
    except Exception as e:
        print(f"   ❌ SPX fetch failed: {e}")
        return False
    
    # Fetch SPY OHLCV
    print("\n4. Fetching SPY OHLCV (1 day, 5-min bars)...")
    try:
        df = adapter.fetch_ohlcv("SPY", period="1d", interval="5m")
        print(f"   ✅ Fetched {len(df)} bars")
        print(f"   📊 Latest bar:")
        latest = df.tail(1)
        print(f"      Close: ${latest['close'][0]:.2f}")
        print(f"      Volume: {latest['volume'][0]:,}")
    except Exception as e:
        print(f"   ❌ OHLCV fetch failed: {e}")
        return False
    
    # Fetch market regime data
    print("\n5. Fetching complete market regime data...")
    try:
        regime_data = get_market_regime_data()
        print(f"   ✅ Market regime data fetched:")
        print(f"      VIX: {regime_data['vix']:.2f}")
        print(f"      SPX: {regime_data['spx']:.2f}")
        print(f"      VIX history: {len(regime_data['vix_history'])} bars")
        print(f"      SPX history: {len(regime_data['spx_history'])} bars")
    except Exception as e:
        print(f"   ❌ Market regime data fetch failed: {e}")
        return False
    
    print("\n" + "✅"*30)
    print("YFINANCE INTEGRATION TEST PASSED")
    print("✅"*30)
    
    return True


def test_sample_options_generator():
    """Test sample options chain generation."""
    print("\n" + "="*60)
    print("TEST 2: SAMPLE OPTIONS GENERATOR")
    print("="*60)
    
    print("\n1. Generating sample options chain...")
    try:
        chain = generate_sample_chain_for_testing(symbol="SPY")
        print(f"   ✅ Generated {len(chain)} options")
        
        # Show statistics
        print(f"\n2. Chain statistics:")
        n_calls = len(chain.filter(chain["option_type"] == "call"))
        n_puts = len(chain.filter(chain["option_type"] == "put"))
        print(f"   Calls: {n_calls}")
        print(f"   Puts: {n_puts}")
        print(f"   Total OI: {chain['open_interest'].sum():,}")
        print(f"   Total Volume: {chain['volume'].sum():,}")
        
        # Show Greeks summary
        print(f"\n3. Greeks summary:")
        print(f"   Gamma range: {chain['gamma'].min():.6f} to {chain['gamma'].max():.6f}")
        print(f"   Delta range: {chain['delta'].min():.4f} to {chain['delta'].max():.4f}")
        print(f"   Vanna range: {chain['vanna'].min():.6f} to {chain['vanna'].max():.6f}")
        
        # Show sample data
        print(f"\n4. Sample ATM options:")
        # Get middle strikes (closest to ATM)
        mid_idx = len(chain) // 2
        atm_options = chain[mid_idx-2:mid_idx+2]
        print(atm_options.select(["strike", "option_type", "delta", "gamma", "open_interest"]))
        
    except Exception as e:
        print(f"   ❌ Sample generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "✅"*30)
    print("SAMPLE OPTIONS GENERATOR TEST PASSED")
    print("✅"*30)
    
    return True


def demo_full_pipeline():
    """Demonstrate full pipeline with free data."""
    print("\n" + "="*60)
    print("DEMO: FULL PIPELINE WITH FREE DATA")
    print("="*60)
    
    print("\n📋 This demonstrates how to:")
    print("   1. Fetch VIX and SPX from yfinance (FREE)")
    print("   2. Generate sample options data for testing")
    print("   3. Feed this into the Hedge Engine")
    print("   4. Train ML models with the complete feature set")
    
    print("\n1. Fetching market data...")
    try:
        adapter = YFinanceAdapter()
        
        # Get SPY data
        spy_data = adapter.fetch_ohlcv("SPY", period="60d", interval="5m")
        spot = float(spy_data["close"].tail(1)[0])
        print(f"   ✅ SPY data: {len(spy_data)} bars, spot={spot:.2f}")
        
        # Get VIX
        vix = adapter.fetch_vix()
        print(f"   ✅ VIX: {vix:.2f}")
        
        # Get SPX history
        spx_history = adapter.fetch_spx_history(period="60d", interval="5m")
        print(f"   ✅ SPX history: {len(spx_history)} bars")
        
    except Exception as e:
        print(f"   ❌ Data fetch failed: {e}")
        return False
    
    print("\n2. Generating sample options chain...")
    try:
        options_chain = generate_sample_chain_for_testing("SPY", spot=spot)
        print(f"   ✅ Options chain: {len(options_chain)} options generated")
    except Exception as e:
        print(f"   ❌ Options generation failed: {e}")
        return False
    
    print("\n3. Data ready for Hedge Engine:")
    print(f"   ✅ Spot price: ${spot:.2f}")
    print(f"   ✅ VIX: {vix:.2f}")
    print(f"   ✅ Options chain: {len(options_chain)} options")
    print(f"   ✅ Historical data: {len(spy_data)} bars")
    
    print("\n4. Next steps:")
    print("   → Feed options_chain to Hedge Engine")
    print("   → Feed SPY data to Liquidity Engine")
    print("   → Feed SPY data to Sentiment Engine")
    print("   → Use VIX/SPX for regime classification in ML")
    print("   → Train ML models with complete 132-feature matrix")
    
    print("\n" + "🎉"*30)
    print("READY FOR ML TRAINING!")
    print("🎉"*30)
    
    return True


def main():
    """Run all tests."""
    print("\n")
    print("█"*60)
    print("  SUPER GNOSIS - YFINANCE INTEGRATION TEST")
    print("█"*60)
    
    print("\n📊 This test suite demonstrates FREE data sources for testing:")
    print("   • yfinance for VIX, SPX, and OHLCV (15-min delay)")
    print("   • Sample options generator for Hedge Engine testing")
    print("   • Complete pipeline without paid subscriptions")
    
    # Run tests
    test1_passed = test_yfinance_connection()
    
    if not test1_passed:
        print("\n❌ YFINANCE TEST FAILED - Check your internet connection")
        sys.exit(1)
    
    test2_passed = test_sample_options_generator()
    
    if not test2_passed:
        print("\n❌ SAMPLE GENERATOR TEST FAILED - Install scipy")
        sys.exit(1)
    
    demo_full_pipeline()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED ✅")
    print("="*60)
    print("\n💡 You can now:")
    print("   1. Test the ML system with FREE data")
    print("   2. Validate the pipeline end-to-end")
    print("   3. Upgrade to paid data when ready for live trading")
    print("\n📖 See DATA_REQUIREMENTS.md for paid data providers")
    print()


if __name__ == "__main__":
    main()
