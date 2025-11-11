#!/usr/bin/env python3
"""
Complete example demonstrating the Gnosis V2 Framework.
Shows the full pipeline: data -> engines -> agents -> trade ideas.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Import the new framework
from src import (
    run_pipeline,
    load_config,
    Bar,
    OptionSnapshot,
)


def create_sample_data():
    """Create realistic sample market data for demonstration."""
    # Generate 120 hours of price data
    np.random.seed(42)
    n_bars = 120
    
    start_time = datetime(2024, 1, 1, 9, 30)
    timestamps = [start_time + timedelta(hours=i) for i in range(n_bars)]
    
    # Generate price with trend and noise
    base_price = 450.0
    trend = np.linspace(0, 10, n_bars)
    noise = np.cumsum(np.random.randn(n_bars) * 0.5)
    prices = base_price + trend + noise
    
    # Generate OHLCV bars
    bars = []
    for i, ts in enumerate(timestamps):
        close = prices[i]
        open_price = prices[i-1] if i > 0 else close
        high = max(open_price, close) * (1 + np.random.uniform(0, 0.01))
        low = min(open_price, close) * (1 - np.random.uniform(0, 0.01))
        volume = np.random.uniform(1e6, 5e6)
        
        bar = Bar(
            ts=ts,
            symbol="SPY",
            open=float(open_price),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume),
            vwap=float((high + low + close) / 3)
        )
        bars.append(bar)
    
    # Generate options chain
    current_price = prices[-1]
    strikes = np.arange(
        current_price * 0.95,
        current_price * 1.05,
        2.5
    )
    
    expiry = (timestamps[-1] + timedelta(days=7)).strftime("%Y-%m-%d")
    
    options = []
    for strike in strikes:
        # Calls
        moneyness = strike / current_price
        iv_base = 0.20 + abs(moneyness - 1.0) * 0.5  # volatility smile
        
        call = OptionSnapshot(
            ts=timestamps[-1],
            symbol="SPY",
            expiry=expiry,
            strike=float(strike),
            right="C",
            bid=max(0.01, (current_price - strike) + 2.0),
            ask=max(0.01, (current_price - strike) + 2.5),
            iv=float(iv_base),
            delta=float(0.5 if strike == current_price else (0.7 if strike < current_price else 0.3)),
            gamma=float(0.05 * np.exp(-abs(strike - current_price) / 10)),
            vega=float(0.1 * np.exp(-abs(strike - current_price) / 10)),
            theta=float(-0.05),
            open_interest=int(np.random.randint(100, 5000)),
            volume=int(np.random.randint(10, 1000))
        )
        options.append(call)
        
        # Puts
        put = OptionSnapshot(
            ts=timestamps[-1],
            symbol="SPY",
            expiry=expiry,
            strike=float(strike),
            right="P",
            bid=max(0.01, (strike - current_price) + 2.0),
            ask=max(0.01, (strike - current_price) + 2.5),
            iv=float(iv_base),
            delta=float(-0.5 if strike == current_price else (-0.3 if strike < current_price else -0.7)),
            gamma=float(0.05 * np.exp(-abs(strike - current_price) / 10)),
            vega=float(0.1 * np.exp(-abs(strike - current_price) / 10)),
            theta=float(-0.05),
            open_interest=int(np.random.randint(100, 5000)),
            volume=int(np.random.randint(10, 1000))
        )
        options.append(put)
    
    # Generate news sentiment scores
    news_scores = list(np.random.uniform(-0.3, 0.7, 20))  # Slightly bullish bias
    
    return bars, options, news_scores


def main():
    """Main demonstration."""
    print("=" * 80)
    print("Gnosis V2 Trading Framework - Complete Example")
    print("=" * 80)
    print()
    
    # Load configuration
    print("[1/6] Loading configuration...")
    try:
        config = load_config()
        print(f"  ✓ Configuration loaded")
        print(f"  - Symbols: {config['symbols']}")
        print(f"  - Risk per trade: {config['risk']['max_risk_per_trade']:.1%}")
        print(f"  - Max open trades: {config['risk']['max_open_trades']}")
    except Exception as e:
        print(f"  ✗ Could not load config: {e}")
        print("  → Using defaults")
        config = {}
    print()
    
    # Generate sample data
    print("[2/6] Generating sample market data...")
    bars, options, news_scores = create_sample_data()
    print(f"  ✓ Generated {len(bars)} price bars")
    print(f"  ✓ Generated {len(options)} option contracts")
    print(f"  ✓ Generated {len(news_scores)} news sentiment scores")
    print(f"  - Current price: ${bars[-1].close:.2f}")
    print(f"  - Options strikes: ${min(o.strike for o in options):.2f} - ${max(o.strike for o in options):.2f}")
    print()
    
    # Run the pipeline
    print("[3/6] Running pipeline...")
    print("  → Computing engine fields (hedge, liquidity, sentiment)...")
    print("  → Running agents (hedge, liquidity, sentiment, composer)...")
    print("  → Generating trade ideas...")
    print()
    
    trade_ideas = run_pipeline(
        symbol="SPY",
        bars=bars,
        options=options,
        news_scores=news_scores
    )
    
    print(f"[4/6] Pipeline complete!")
    print(f"  ✓ Generated {len(trade_ideas)} trade idea(s)")
    print()
    
    # Display results
    print("[5/6] Trade Ideas:")
    print("-" * 80)
    
    if not trade_ideas:
        print("  No trade ideas generated (conviction may be too low or neutral thesis)")
    else:
        for i, idea in enumerate(trade_ideas, 1):
            print(f"\n  Idea #{i}:")
            print(f"  - Symbol: {idea.symbol}")
            print(f"  - Type: {idea.idea_type}")
            print(f"  - Strategy: {idea.strategy}")
            print(f"  - Entry Cost: ${idea.entry_cost:.2f}")
            print(f"  - Target: ${idea.exit_target:.2f}")
            print(f"  - Stop Loss: ${idea.stop_loss:.2f}")
            print(f"  - Projected P&L: ${idea.projected_pnl:.2f}")
            print(f"  - Recommended Size: {idea.recommended_size}")
            print(f"  - Time Horizon: {idea.ttl_days:.1f} days")
            print(f"  - Legs: {len(idea.legs)}")
            for j, leg in enumerate(idea.legs, 1):
                print(f"    {j}. {leg}")
    
    print()
    print("-" * 80)
    
    # Summary
    print()
    print("[6/6] Summary")
    print("=" * 80)
    print()
    print("Framework Architecture Demonstrated:")
    print("  ✓ Data Layer: Bar and OptionSnapshot schemas")
    print("  ✓ Engine Layer: Hedge, Liquidity, Sentiment engines")
    print("  ✓ Agent Layer: Specialized agents + Composer")
    print("  ✓ Trade Layer: Trade construction with risk management")
    print()
    print("Next Steps:")
    print("  1. Connect to live data feeds (Alpaca API)")
    print("  2. Implement backtesting with historical data")
    print("  3. Add more sophisticated Wyckoff phase detection")
    print("  4. Integrate news sentiment API (FinBERT)")
    print("  5. Build dashboard for visualization")
    print("  6. Add real-time monitoring and alerts")
    print()
    print("For more information:")
    print("  - See src/README.md for architecture details")
    print("  - See src/config/settings.yaml for configuration options")
    print("  - See src/pipeline.py for orchestration logic")
    print()


if __name__ == "__main__":
    main()
