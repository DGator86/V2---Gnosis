#!/usr/bin/env python3
"""
Full Data Pipeline
==================

End-to-end pipeline that:
1. Fetches real market data (L0 → L1)
2. Generates L3 features from all engines
3. Runs comparative backtest
4. Analyzes results

Usage:
    python run_full_pipeline.py SPY 2024-10-01 30

This will:
- Fetch 30 days of hourly SPY data starting 2024-10-01
- Process through hedge, liquidity, sentiment engines
- Run 6 agent configurations in parallel
- Show performance comparison
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# Import our components
from gnosis.ingest.adapters.unified_data_adapter import UnifiedDataAdapter
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
from gnosis.feature_store.store import FeatureStore
from gnosis.schemas.base import L3Canonical


def fetch_data(symbol: str, start_date: str, num_days: int, interval: str = "1h") -> pd.DataFrame:
    """
    Step 1: Fetch real market data
    
    Returns DataFrame with L1 format
    """
    print("\n" + "="*70)
    print("  STEP 1: FETCH MARKET DATA")
    print("="*70)
    
    adapter = UnifiedDataAdapter()
    paths = adapter.fetch_range(symbol, start_date, num_days, interval)
    
    # Load the data we just saved
    l1_file = Path("data_l1") / f"l1_{start_date}.parquet"
    df = pd.read_parquet(l1_file)
    
    print(f"\n✅ Loaded {len(df)} bars from {l1_file}")
    print(f"   Date range: {df['t_event'].min()} to {df['t_event'].max()}")
    print(f"   Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
    
    return df


def generate_l3_features(df: pd.DataFrame, symbol: str) -> int:
    """
    Step 2: Generate L3 features from L1 data
    
    Processes each bar through:
    - Hedge engine (options Greeks, dealer positioning)
    - Liquidity engine (volume profiles, Amihud illiquidity)
    - Sentiment engine (momentum, volatility, RSI)
    
    Returns number of feature rows generated
    """
    print("\n" + "="*70)
    print("  STEP 2: GENERATE L3 FEATURES")
    print("="*70)
    
    fs = FeatureStore()
    
    # Need at least 50 bars of history for engines
    min_history = 50
    
    # Synthetic options chain (in production, fetch from real options API)
    spot_price = df["price"].iloc[-1]
    strikes = [spot_price * (1 + i * 0.01) for i in range(-10, 11)]
    expiry = datetime.now() + timedelta(days=7)
    
    chain = pd.DataFrame({
        "strike": strikes,
        "expiry": expiry,
        "iv": [0.20] * len(strikes),
        "delta": [0.5] * len(strikes),
        "gamma": [0.01] * len(strikes),
        "vega": [0.02] * len(strikes),
        "theta": [-0.01] * len(strikes),
        "open_interest": [100] * len(strikes)
    })
    
    print(f"Processing {len(df)} bars...")
    print(f"  - Need {min_history} bars history, so starting from bar {min_history}")
    print(f"  - Will generate {len(df) - min_history} L3 rows")
    
    count = 0
    for i in range(min_history, len(df)):
        if i % 20 == 0:
            print(f"  Progress: {i - min_history + 1}/{len(df) - min_history} rows...", end="\r")
        
        t = df.loc[i, "t_event"]
        price = df.loc[i, "price"]
        
        # Get 60-bar window for engines
        window = df.iloc[max(0, i-60):i+1].copy()
        
        # Compute features from all three engines
        hedge = compute_hedge_v0(symbol, t, price, chain)
        liq = compute_liquidity_v0(symbol, t, window)
        sent = compute_sentiment_v0(symbol, t, window)
        
        # Create L3 row
        row = L3Canonical(
            symbol=symbol,
            bar=t,
            hedge=hedge,
            liquidity=liq,
            sentiment=sent
        )
        
        # Write to feature store
        fs.write(row)
        count += 1
    
    print(f"\n✅ Generated {count} L3 feature rows")
    print(f"   Stored in: data/date=2024-*/symbol={symbol}/feature_set_id=v0.1.0/")
    
    return count


def run_comparative_backtest(symbol: str, start_date: str):
    """
    Step 3: Run comparative backtest
    
    Tests all 6 agent configurations:
    - baseline (3-agent: hedge, liquidity, sentiment)
    - wyckoff_added (4-agent: + wyckoff)
    - markov_added (4-agent: + markov)
    - full_5agent (5-agent: all)
    - full_high_bar (5-agent with 3-of-5 voting)
    - conservative (5-agent with high thresholds)
    """
    print("\n" + "="*70)
    print("  STEP 3: RUN COMPARATIVE BACKTEST")
    print("="*70)
    
    # Import here to avoid circular dependencies
    from gnosis.backtest.comparative_backtest import compare_strategies
    
    # Run the backtest
    results_df = compare_strategies(symbol, start_date)
    
    print(f"\n{'='*70}")
    print("  RESULTS SUMMARY")
    print(f"{'='*70}\n")
    print(results_df.to_string(index=False))
    
    # Save results
    import json
    output_file = f"comparative_backtest_{symbol}_{start_date}.json"
    with open(output_file, 'w') as f:
        json.dump(results_df.to_dict(orient='records'), f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Highlight winner
    if not results_df.empty:
        winner = results_df.iloc[0]
        print(f"\n🏆 WINNER: {winner['name']}")
        print(f"   Sharpe: {winner['sharpe']:.3f}")
        print(f"   PnL: ${winner['pnl']:.2f}")
        print(f"   Trades: {winner['num_trades']}")
        print(f"   Win Rate: {winner['win_rate']:.1%}")
    
    return results_df


def analyze_results():
    """
    Step 4: Analyze and interpret results
    
    Reads the comparison results and provides interpretation
    """
    print("\n" + "="*70)
    print("  STEP 4: ANALYSIS & INTERPRETATION")
    print("="*70)
    
    print("""
📊 INTERPRETATION GUIDE:

1. **Number of Trades**
   - More trades ≠ better (could be overtrading)
   - Fewer trades with high conviction = ideal
   - Zero trades on noisy data = good filtering

2. **Trade Quality Metrics**
   - Win rate: % of profitable trades
   - Avg P&L: Average profit per trade
   - Sharpe ratio: Risk-adjusted returns

3. **Agent Performance**
   - Baseline (3-agent): Current production system
   - Wyckoff/Markov added: New candidates
   - Compare: Does adding new agents improve metrics?

4. **Decision Framework**
   ✅ Integrate if: Higher Sharpe, better win rate, similar/fewer trades
   ⚠️  Calibrate if: More trades but mixed quality
   ❌ Keep in sandbox if: No improvement or worse performance

5. **Next Steps Based on Results**
   - Winner clear → Follow WYCKOFF_MARKOV_INTEGRATION.md
   - Mixed results → Run more days, different symbols
   - Baseline wins → Current 3-agent system is optimal
   - Need more data → Extend backtest period
""")


def main():
    parser = argparse.ArgumentParser(
        description="Run full trading system pipeline: data → features → backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full October 2024 analysis
  python run_full_pipeline.py SPY 2024-10-01 30

  # Single day quick test
  python run_full_pipeline.py SPY 2024-10-15 1

  # Different symbol
  python run_full_pipeline.py QQQ 2024-10-01 30
        """
    )
    
    parser.add_argument("symbol", help="Trading symbol (e.g., SPY, QQQ)")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("num_days", type=int, help="Number of days to fetch")
    parser.add_argument("--interval", default="1h", help="Bar interval (default: 1h)")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip data fetch (use existing)")
    parser.add_argument("--skip-features", action="store_true", help="Skip feature generation")
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("  🚀 AGENTIC TRADING SYSTEM - FULL PIPELINE")
    print("="*70)
    print(f"  Symbol: {args.symbol}")
    print(f"  Period: {args.start_date} + {args.num_days} days")
    print(f"  Interval: {args.interval}")
    print("="*70)
    
    try:
        # Step 1: Fetch data
        if not args.skip_fetch:
            df = fetch_data(args.symbol, args.start_date, args.num_days, args.interval)
        else:
            print("\n⏭️  Skipping data fetch (using existing)")
            l1_file = Path("data_l1") / f"l1_{args.start_date}.parquet"
            df = pd.read_parquet(l1_file)
            print(f"   Loaded {len(df)} bars from {l1_file}")
        
        # Step 2: Generate L3 features
        if not args.skip_features:
            num_features = generate_l3_features(df, args.symbol)
        else:
            print("\n⏭️  Skipping feature generation (using existing)")
        
        # Step 3: Run comparative backtest
        results = run_comparative_backtest(args.symbol, args.start_date)
        
        # Step 4: Analyze results
        analyze_results()
        
        print("\n" + "="*70)
        print("  ✅ PIPELINE COMPLETE!")
        print("="*70)
        print("""
Next steps:
1. Review the comparative backtest results above
2. Check SANDBOX_TESTING_GUIDE.md for decision framework
3. If winner is clear, follow WYCKOFF_MARKOV_INTEGRATION.md
4. If inconclusive, run more days or different symbols
        """)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
