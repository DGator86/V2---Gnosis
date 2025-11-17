"""
FREE Data Pipeline Demo

Demonstrates the complete FREE data pipeline with all integrated sources.

This script shows:
1. How to fetch data from ALL free sources
2. How to use DataSourceManager for unified access
3. How to integrate with ML feature engineering
4. Complete $0/month data pipeline

Usage:
    python examples/free_data_pipeline_demo.py

Optional environment variables:
    FRED_API_KEY - FRED API key (free from fred.stlouisfed.org)
    IEX_API_TOKEN - IEX Cloud token (free tier at iexcloud.io)
    REDDIT_CLIENT_ID - Reddit app client ID (free from reddit.com/prefs/apps)
    REDDIT_CLIENT_SECRET - Reddit app secret
"""

import os
from datetime import datetime, date, timedelta
from loguru import logger

# Configure logger
logger.add("free_data_demo.log", rotation="10 MB")

# Import data source manager
from engines.inputs.data_source_manager import DataSourceManager

# Import individual adapters for detailed examples
from engines.inputs.yfinance_adapter import YFinanceAdapter
from engines.inputs.yahoo_options_adapter import YahooOptionsAdapter
from engines.inputs.fred_adapter import FREDAdapter
from engines.inputs.dark_pool_adapter import DarkPoolAdapter
from engines.inputs.short_volume_adapter import ShortVolumeAdapter
from engines.inputs.stocktwits_adapter import StockTwitsAdapter
from engines.inputs.greekcalc_adapter import GreekCalcAdapter

# Import ML features
from ml.features.ta_indicators import TAIndicators


def print_section(title: str):
    """Print section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def demo_yfinance():
    """Demo yfinance adapter."""
    print_section("1. YFINANCE ADAPTER - FREE Market Data")
    
    adapter = YFinanceAdapter()
    
    # Fetch VIX and SPX
    vix = adapter.fetch_vix()
    spx = adapter.fetch_spx()
    
    print(f"📊 Market Regime:")
    print(f"   VIX: {vix:.2f}")
    print(f"   SPX: {spx:.2f}")
    
    # Fetch historical data
    df_spy = adapter.fetch_history("SPY", period="5d", interval="1d")
    
    print(f"\n📈 SPY Last 5 Days:")
    print(df_spy.select(["timestamp", "open", "high", "low", "close", "volume"]))


def demo_yahoo_options():
    """Demo Yahoo options adapter."""
    print_section("2. YAHOO OPTIONS - FREE Options Chains")
    
    adapter = YahooOptionsAdapter()
    
    # Fetch options chain
    chain = adapter.fetch_options_chain(
        symbol="SPY",
        min_days_to_expiry=15,
        max_days_to_expiry=45
    )
    
    print(f"📋 SPY Options Chain:")
    print(f"   Total Options: {len(chain)}")
    
    # Show ATM options
    if not chain.is_empty():
        spot = chain.select("underlying_price").head(1).item()
        atm_chain = chain.filter(
            (chain["strike"] >= spot * 0.98) &
            (chain["strike"] <= spot * 1.02)
        )
        
        print(f"\n   ATM Options (spot=${spot:.2f}):")
        print(atm_chain.select([
            "option_type", "strike", "bid", "ask",
            "delta", "gamma", "theta", "implied_vol"
        ]).head(10))


def demo_fred():
    """Demo FRED adapter."""
    print_section("3. FRED ADAPTER - FREE Macro Data")
    
    fred_key = os.getenv("FRED_API_KEY")
    
    if not fred_key:
        print("⚠️  FRED_API_KEY not set. Get free key at: https://fred.stlouisfed.org/")
        print("   Skipping FRED demo...")
        return
    
    adapter = FREDAdapter(api_key=fred_key)
    
    # Fetch macro data
    macro = adapter.fetch_macro_regime_data(lookback_days=365)
    
    print(f"💰 Macro Economic Data:")
    print(f"   Fed Funds Rate: {macro['fed_funds_rate']:.2f}%")
    print(f"   10Y Treasury: {macro['treasury_10y']:.2f}%")
    print(f"   2Y Treasury: {macro['treasury_2y']:.2f}%")
    print(f"   Yield Curve Slope: {macro['yield_curve_slope']:+.2f}%")
    print(f"   Unemployment Rate: {macro['unemployment']:.1f}%")
    print(f"   BAA Credit Spread: {macro['baa_spread']:.2f}%")
    print(f"   Recession Probability: {macro['recession_probability']:.1%}")


def demo_dark_pool():
    """Demo dark pool adapter."""
    print_section("4. DARK POOL - FREE Institutional Flow Estimation")
    
    adapter = DarkPoolAdapter()
    
    # Estimate dark pool pressure
    pressure = adapter.estimate_dark_pool_pressure("SPY")
    
    print(f"🏊 Dark Pool Metrics:")
    print(f"   Dark Pool Ratio: {pressure['dark_pool_ratio']:.2%}")
    print(f"   Net Dark Buying: {pressure['net_dark_buying']:+.3f}")
    print(f"   Accumulation Score: {pressure['accumulation_score']:.3f}")
    print(f"   Distribution Score: {pressure['distribution_score']:.3f}")
    
    if pressure['accumulation_score'] > 0.6:
        print(f"   🟢 Signal: Strong institutional accumulation")
    elif pressure['distribution_score'] > 0.6:
        print(f"   🔴 Signal: Strong institutional distribution")


def demo_short_volume():
    """Demo short volume adapter."""
    print_section("5. SHORT VOLUME - FREE FINRA Data")
    
    adapter = ShortVolumeAdapter()
    
    # Fetch recent short volume
    test_date = date.today() - timedelta(days=3)
    short_vol = adapter.fetch_short_volume("SPY", date=test_date)
    
    if short_vol:
        print(f"📊 Short Volume for {test_date}:")
        print(f"   Short Volume: {short_vol['short_volume']:,}")
        print(f"   Total Volume: {short_vol['total_volume']:,}")
        print(f"   Short Ratio: {short_vol['short_ratio']:.2%}")
    else:
        print(f"⚠️  Short volume data not available for {test_date}")
        print(f"   (FINRA data has 3-day delay)")
    
    # Calculate squeeze pressure
    print(f"\n🚀 Short Squeeze Analysis:")
    squeeze = adapter.calculate_short_squeeze_pressure("SPY", lookback_days=10)
    
    print(f"   Avg Short Ratio: {squeeze['avg_short_ratio']:.2%}")
    print(f"   Short Ratio Trend: {squeeze['short_ratio_trend']:+.2%}")
    print(f"   Squeeze Pressure: {squeeze['squeeze_pressure']:.3f}")
    print(f"   Covering Signal: {squeeze['covering_signal']}")


def demo_stocktwits():
    """Demo StockTwits adapter."""
    print_section("6. STOCKTWITS - FREE Retail Sentiment")
    
    adapter = StockTwitsAdapter(use_cache=False)
    
    try:
        # Fetch sentiment
        sentiment = adapter.fetch_sentiment("SPY", limit=30)
        
        print(f"💬 StockTwits Sentiment:")
        print(f"   Total Messages: {sentiment.total_messages}")
        print(f"   Bullish: {sentiment.bullish_messages} ({sentiment.bullish_messages/max(1, sentiment.total_messages):.1%})")
        print(f"   Bearish: {sentiment.bearish_messages} ({sentiment.bearish_messages/max(1, sentiment.total_messages):.1%})")
        print(f"   Neutral: {sentiment.neutral_messages}")
        print(f"   Sentiment Score: {sentiment.sentiment_score:+.3f} (-1 to +1)")
        print(f"   Confidence: {sentiment.confidence:.3f}")
        print(f"   Message Velocity: {sentiment.message_velocity:.1f} msg/hr")
        print(f"   Trending: {'🔥 YES' if sentiment.is_trending else 'No'}")
        
        # Fetch multi-symbol
        print(f"\n📊 Multi-Symbol Sentiment:")
        df_multi = adapter.fetch_multi_symbol_sentiment(
            symbols=["SPY", "QQQ", "AAPL", "TSLA", "NVDA"],
            limit_per_symbol=20
        )
        
        print(df_multi.select([
            "symbol", "sentiment_score", "total_messages",
            "is_trending", "message_velocity"
        ]))
        
    finally:
        adapter.close()


def demo_greeks():
    """Demo Greeks calculator."""
    print_section("7. GREEKS CALCULATOR - FREE Validation")
    
    adapter = GreekCalcAdapter(risk_free_rate=0.05)
    
    # Calculate Greeks for ATM call
    spot = 450.0
    strike = 450.0
    expiry = date.today() + timedelta(days=30)
    
    greeks = adapter.calculate_greeks(
        spot_price=spot,
        strike=strike,
        expiry_date=expiry,
        option_type="call",
        volatility=0.25
    )
    
    print(f"🎯 ATM Call Greeks (Strike=${strike}, 30 DTE):")
    print(f"   Delta: {greeks['delta']:.4f}")
    print(f"   Gamma: {greeks['gamma']:.6f}")
    print(f"   Theta: {greeks['theta']:.4f} (daily decay)")
    print(f"   Vega: {greeks['vega']:.4f} (per 1% IV change)")
    print(f"   Rho: {greeks['rho']:.4f} (per 1% rate change)")


def demo_technical_indicators():
    """Demo technical indicators."""
    print_section("8. TECHNICAL INDICATORS - 130+ FREE Indicators")
    
    # Fetch OHLCV data
    yf = YFinanceAdapter()
    df_ohlcv = yf.fetch_history("SPY", period="60d", interval="1d")
    
    # Add technical indicators
    ta = TAIndicators()
    
    print(f"📈 Adding Technical Indicators...")
    print(f"   Original columns: {len(df_ohlcv.columns)}")
    
    df_with_ta = ta.add_all_indicators(df_ohlcv)
    
    added = len(df_with_ta.columns) - len(df_ohlcv.columns)
    print(f"   After ta indicators: {len(df_with_ta.columns)}")
    print(f"   Added: {added} indicators")
    
    # Show sample indicators
    print(f"\n   Sample Technical Indicators:")
    sample_cols = [
        "close", "ta_trend_macd", "ta_momentum_rsi",
        "ta_volatility_atr", "ta_volume_obv"
    ]
    
    available_cols = [col for col in sample_cols if col in df_with_ta.columns]
    print(df_with_ta.select(available_cols).tail(5))


def demo_unified_manager():
    """Demo unified data source manager."""
    print_section("9. UNIFIED DATA SOURCE MANAGER - Complete Integration")
    
    # Initialize manager with all FREE sources
    manager = DataSourceManager(
        fred_api_key=os.getenv("FRED_API_KEY"),
        iex_api_token=os.getenv("IEX_API_TOKEN"),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent="FreeDataDemo/1.0"
    )
    
    # Check source status
    print(f"📊 Data Source Status:")
    df_status = manager.get_source_status()
    
    for row in df_status.iter_rows(named=True):
        status_icon = "✅" if row["is_available"] else "❌"
        print(f"   {status_icon} {row['source_type']}: {'Available' if row['is_available'] else 'Not Available'}")
    
    # Fetch unified data
    print(f"\n🎯 Unified Data for SPY:")
    data = manager.fetch_unified_data(
        symbol="SPY",
        include_options=True,
        include_sentiment=True,
        include_macro=True
    )
    
    print(f"\n   OHLCV:")
    print(f"      Close: ${data.close:.2f}")
    print(f"      Volume: {data.volume:,}")
    
    if data.vix:
        print(f"\n   Regime:")
        print(f"      VIX: {data.vix:.2f}")
        print(f"      SPX: {data.spx:.2f}")
    
    if data.fed_funds_rate:
        print(f"\n   Macro:")
        print(f"      Fed Funds: {data.fed_funds_rate:.2f}%")
        print(f"      10Y Treasury: {data.treasury_10y:.2f}%")
        print(f"      Yield Curve: {data.yield_curve_slope:+.2f}%")
    
    if data.options_chain_available:
        print(f"\n   Options:")
        print(f"      Available: Yes")
        print(f"      Num Options: {data.num_options}")
    
    if data.stocktwits_sentiment is not None:
        print(f"\n   Sentiment:")
        print(f"      StockTwits: {data.stocktwits_sentiment:+.3f}")
        if data.wsb_sentiment is not None:
            print(f"      WSB: {data.wsb_sentiment:+.3f} ({data.wsb_mentions} mentions)")
    
    if data.dark_pool_ratio:
        print(f"\n   Dark Pool:")
        print(f"      Ratio: {data.dark_pool_ratio:.2%}")
        print(f"      Pressure: {data.dark_pool_pressure:.3f}")
    
    if data.short_volume_ratio:
        print(f"\n   Short Interest:")
        print(f"      Short Ratio: {data.short_volume_ratio:.2%}")
        print(f"      Squeeze Pressure: {data.short_squeeze_pressure:.3f}")
    
    print(f"\n   📦 Data Sources Used: {', '.join(data.data_sources_used)}")
    print(f"   ✅ Validation: {'PASSED' if data.validation_passed else 'FAILED'}")


def demo_cost_analysis():
    """Demo cost analysis."""
    print_section("10. COST ANALYSIS - $0/month Solution")
    
    print("💰 FREE Data Pipeline Cost Breakdown:\n")
    
    sources = [
        ("yfinance", "VIX, SPX, OHLCV", "$0/month", "Unlimited"),
        ("Yahoo Finance", "Options Chains + Greeks", "$0/month", "Reasonable limits"),
        ("FRED", "Macro Economic Data", "$0/month", "Unlimited with free API key"),
        ("StockTwits", "Retail Sentiment", "$0/month", "200 req/hour"),
        ("FINRA", "Short Volume (Official)", "$0/month", "Daily updates"),
        ("Dark Pool Estimation", "Institutional Flow", "$0/month", "Unlimited"),
        ("ta Library", "130+ Technical Indicators", "$0/month", "Unlimited"),
        ("greekcalc", "Greeks Validation", "$0/month", "Unlimited"),
    ]
    
    for name, features, cost, limits in sources:
        print(f"   ✅ {name:20s} | {features:30s} | {cost:12s} | {limits}")
    
    print(f"\n" + "-"*70)
    print(f"   TOTAL MONTHLY COST: $0.00")
    print(f"   " + "-"*70)
    
    print(f"\n📊 Compare to Paid Alternatives:")
    paid = [
        ("Polygon.io", "$249/month"),
        ("CBOE DataShop", "$100-500/month"),
        ("ORATS", "$99-299/month"),
        ("Quiver Quant", "$50-200/month"),
    ]
    
    total_paid = 0
    for name, cost_str in paid:
        cost_val = int(cost_str.split("-")[0].replace("$", "").replace("/month", ""))
        total_paid += cost_val
        print(f"   ❌ {name:20s} | {cost_str}")
    
    print(f"\n   Paid Alternative Total: ${total_paid}+/month")
    print(f"\n   💵 YOUR SAVINGS: ${total_paid}+/month with FREE pipeline!")


def main():
    """Run all demos."""
    print("\n" + "🚀"*35)
    print("  FREE DATA PIPELINE DEMO - $0/month Complete Solution")
    print("🚀"*35)
    
    # Run all demos
    demo_yfinance()
    demo_yahoo_options()
    demo_fred()
    demo_dark_pool()
    demo_short_volume()
    demo_stocktwits()
    demo_greeks()
    demo_technical_indicators()
    demo_unified_manager()
    demo_cost_analysis()
    
    # Final summary
    print_section("DEMO COMPLETE")
    
    print("✅ All FREE data sources demonstrated")
    print("✅ Complete $0/month pipeline operational")
    print("✅ Ready for production ML training")
    print("\nNext steps:")
    print("  1. Set optional API keys (FRED, IEX, Reddit) for full features")
    print("  2. Integrate with ML feature engineering")
    print("  3. Train models with unified data")
    print("  4. Deploy to production")
    print("\nDocumentation:")
    print("  - FREE_DATA_SOURCES.md - Complete catalog")
    print("  - DATA_REQUIREMENTS.md - Cost analysis")
    print("  - ML_FEATURE_MATRIX.md - Feature mapping")


if __name__ == "__main__":
    main()
