#!/usr/bin/env python3
"""
Run comparative backtest on multiple days of real market data.
"""
import sys
import json
import subprocess
from pathlib import Path
from collections import defaultdict

def run_backtest_for_date(date: str, symbol: str = "SPY"):
    """Run comparative backtest for a single date."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING {symbol} on {date}")
    print(f"{'='*60}\n")
    
    try:
        # Run the comparative backtest
        result = subprocess.run(
            ["./run_comparison.sh", symbol, date],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"⚠ Backtest failed for {date}")
            print(result.stderr)
            return None
        
        # Load results
        results_file = f"comparative_backtest_{symbol}_{date}.json"
        if Path(results_file).exists():
            with open(results_file) as f:
                data = json.load(f)
            print(f"✓ Results saved to {results_file}")
            return data
        else:
            print(f"⚠ No results file found: {results_file}")
            return None
            
    except Exception as e:
        print(f"✗ Error running backtest for {date}: {e}")
        return None

def aggregate_results(results_by_date):
    """Aggregate results across all dates."""
    print(f"\n{'='*70}")
    print(f"MULTI-DAY AGGREGATE RESULTS")
    print(f"{'='*70}\n")
    
    # Aggregate by configuration
    configs = defaultdict(lambda: {
        'total_trades': 0,
        'total_pnl': 0.0,
        'wins': 0,
        'losses': 0,
        'days_with_trades': 0,
        'dates': []
    })
    
    for date, data in results_by_date.items():
        if data is None:
            continue
        
        # Handle both list and dict formats
        config_list = data if isinstance(data, list) else data.get('configurations', [])
        
        for config in config_list:
            name = config['name']
            trades = config['num_trades']
            pnl = config['pnl']
            
            configs[name]['total_trades'] += trades
            configs[name]['total_pnl'] += pnl
            
            # Calculate wins/losses from individual trades if available
            # Otherwise estimate from win_rate
            if 'num_wins' in config:
                configs[name]['wins'] += config['num_wins']
                configs[name]['losses'] += config['num_losses']
            elif trades > 0 and config['win_rate'] > 0:
                wins = int(trades * config['win_rate'] / 100)
                configs[name]['wins'] += wins
                configs[name]['losses'] += (trades - wins)
            
            if trades > 0:
                configs[name]['days_with_trades'] += 1
                configs[name]['dates'].append(date)
    
    # Print summary table
    print(f"{'Configuration':<25} | {'Trades':<7} | {'P&L':<10} | {'Win Rate':<8} | {'Days Active'}")
    print("-" * 70)
    
    for name, stats in sorted(configs.items()):
        total_trades = stats['total_trades']
        total_pnl = stats['total_pnl']
        wins = stats['wins']
        losses = stats['losses']
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        days_active = stats['days_with_trades']
        
        print(f"{name:<25} | {total_trades:>7} | ${total_pnl:>9.2f} | {win_rate:>7.1f}% | {days_active}/5")
    
    print(f"\n{'='*70}\n")
    
    # Save aggregate results
    output = {
        'total_days': len(results_by_date),
        'successful_days': len([d for d in results_by_date.values() if d is not None]),
        'configurations': configs
    }
    
    with open('multi_day_aggregate_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print("✓ Aggregate results saved to multi_day_aggregate_results.json\n")
    return configs

def main():
    dates = ['2025-10-24', '2025-10-27', '2025-10-28', '2025-10-29', '2025-10-30']
    symbol = 'SPY'
    
    results_by_date = {}
    
    for date in dates:
        results = run_backtest_for_date(date, symbol)
        results_by_date[date] = results
    
    # Aggregate and summarize
    if any(r is not None for r in results_by_date.values()):
        aggregate_results(results_by_date)
    else:
        print("\n⚠ No successful backtests to aggregate\n")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
