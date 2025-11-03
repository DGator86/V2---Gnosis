"""
Backtest CLI runner

Usage:
    python -m gnosis.backtest --date 2025-11-03 --symbol SPY
"""
from .replay_v0 import backtest_day
import argparse
import json

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run event-time backtest")
    ap.add_argument("--symbol", default="SPY", help="Trading symbol")
    ap.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    ap.add_argument("--l1-path", default="data_l1", help="Path to L1 data directory")
    ap.add_argument("--feature-set", default="v0.1.0", help="Feature set ID")
    
    args = ap.parse_args()
    
    print(f"Running backtest for {args.symbol} on {args.date}...")
    print("-" * 60)
    
    result = backtest_day(
        symbol=args.symbol,
        date=args.date,
        l1_path=args.l1_path,
        feature_set_id=args.feature_set
    )
    
    # Pretty print results
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"\n📊 Backtest Results for {result['symbol']} on {result['date']}")
        print("=" * 60)
        print(f"P&L:              ${result['pnl']:.2f}")
        print(f"Num Trades:       {result['num_trades']}")
        print(f"Win Rate:         {result['win_rate']:.1%}")
        print(f"Avg Win:          ${result['avg_win']:.2f}")
        print(f"Avg Loss:         ${result['avg_loss']:.2f}")
        print(f"Sharpe (intraday):{result['sharpe_like_intraday']:.2f}")
        print(f"Max Drawdown:     ${result['max_drawdown']:.2f}")
        
        if result['trades']:
            print(f"\n📋 Trades ({len(result['trades'])}):")
            print("-" * 60)
            for i, trade in enumerate(result['trades'], 1):
                dir_str = "LONG" if trade['direction'] > 0 else "SHORT"
                print(f"\n  Trade #{i} ({dir_str}):")
                print(f"    Entry:  {trade['t_entry']} @ ${trade['entry_px']:.2f}")
                print(f"    Exit:   {trade['t_exit']} @ ${trade['exit_px']:.2f}")
                print(f"    P&L:    ${trade['pnl']:.2f}")
                print(f"    Reason: {trade['exit_reason']}")
        
        # Optionally save full JSON
        print(f"\n💾 Full results saved to: backtest_{args.symbol}_{args.date}.json")
        with open(f"backtest_{args.symbol}_{args.date}.json", "w") as f:
            json.dump(result, indent=2, fp=f, default=str)