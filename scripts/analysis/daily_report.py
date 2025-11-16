#!/usr/bin/env python3
"""
Daily Report Generator for Phase 3 Paper Trading

Analyzes accumulated JSONL data and generates comprehensive daily reports.

Usage:
    python scripts/analysis/daily_report.py
    python scripts/analysis/daily_report.py --days 7
    python scripts/analysis/daily_report.py --output reports/
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file into list of dictionaries."""
    if not file_path.exists():
        return []
    
    with open(file_path) as f:
        return [json.loads(line) for line in f]


def analyze_strategy_distribution(trades: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count strategy types across all trades."""
    strategies = [t["trade"]["strategy_type"] for t in trades]
    return dict(Counter(strategies))


def analyze_regime_correlation(contexts: List[Dict[str, Any]], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze strategy selection by regime."""
    regime_strategies = defaultdict(list)
    
    for context, trade_set in zip(contexts, trades):
        ctx = context["context"]
        regime_key = f"{ctx['volatility_regime']}_{ctx['direction']}"
        strategy = trade_set["trade"]["strategy_type"]
        regime_strategies[regime_key].append(strategy)
    
    # Count strategies per regime
    regime_counts = {}
    for regime, strategies in regime_strategies.items():
        regime_counts[regime] = dict(Counter(strategies))
    
    return regime_counts


def analyze_risk_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze risk metrics across all trades."""
    max_losses = [t["trade"].get("max_loss", 0) for t in trades if t["trade"].get("max_loss")]
    max_profits = [t["trade"].get("max_profit", 0) for t in trades if t["trade"].get("max_profit")]
    breakevens = [be for t in trades for be in t["trade"].get("breakeven_prices", [])]
    
    return {
        "max_loss_mean": sum(max_losses) / len(max_losses) if max_losses else 0,
        "max_loss_min": min(max_losses) if max_losses else 0,
        "max_loss_max": max(max_losses) if max_losses else 0,
        "max_profit_mean": sum(max_profits) / len(max_profits) if max_profits else 0,
        "max_profit_min": min(max_profits) if max_profits else 0,
        "max_profit_max": max(max_profits) if max_profits else 0,
        "breakeven_count": len(breakevens),
        "trade_count": len(trades),
    }


def analyze_exit_rules(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze exit rule configuration."""
    profit_targets = [t["trade"].get("profit_target_pct") for t in trades if t["trade"].get("profit_target_pct")]
    stop_losses = [t["trade"].get("stop_loss_pct") for t in trades if t["trade"].get("stop_loss_pct")]
    trailing_stops = [t["trade"].get("trailing_stop_pct") for t in trades if t["trade"].get("trailing_stop_pct")]
    
    return {
        "profit_target_mean": sum(profit_targets) / len(profit_targets) if profit_targets else 0,
        "stop_loss_mean": sum(stop_losses) / len(stop_losses) if stop_losses else 0,
        "trailing_stop_mean": sum(trailing_stops) / len(trailing_stops) if trailing_stops else 0,
    }


def analyze_execution_quality(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze execution quality metrics."""
    if not orders:
        return {"order_count": 0}
    
    filled = [o for o in orders if o["order"]["status"] == "filled"]
    rejected = [o for o in orders if o["order"]["status"] == "rejected"]
    
    slippages = [o["order"].get("estimated_slippage", 0) for o in filled if o["order"].get("estimated_slippage")]
    commissions = [o["order"].get("total_commission", 0) for o in filled if o["order"].get("total_commission")]
    
    return {
        "order_count": len(orders),
        "filled_count": len(filled),
        "rejected_count": len(rejected),
        "fill_rate": len(filled) / len(orders) if orders else 0,
        "avg_slippage": sum(slippages) / len(slippages) if slippages else 0,
        "total_commission": sum(commissions),
    }


def generate_report(runs_dir: Path, days: int = 30, output_dir: Optional[Path] = None) -> str:
    """
    Generate comprehensive daily report.
    
    Args:
        runs_dir: Directory containing run data (e.g., runs/)
        days: Number of days to include in analysis
        output_dir: Optional output directory for report
    
    Returns:
        Report as formatted string
    """
    # Collect all data from last N days
    all_contexts = []
    all_trades = []
    all_orders = []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    for date_dir in runs_dir.iterdir():
        if not date_dir.is_dir():
            continue
        
        # Parse date from directory name
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        
        if start_date <= dir_date <= end_date:
            # Load data from this date
            contexts = load_jsonl(date_dir / "SPY_context.jsonl")
            trades = load_jsonl(date_dir / "SPY_trades.jsonl")
            orders = load_jsonl(date_dir / "SPY_orders.jsonl")
            
            all_contexts.extend(contexts)
            all_trades.extend(trades)
            all_orders.extend(orders)
    
    # Analyze
    strategy_dist = analyze_strategy_distribution(all_trades)
    regime_corr = analyze_regime_correlation(all_contexts, all_trades) if all_contexts else {}
    risk_metrics = analyze_risk_metrics(all_trades)
    exit_rules = analyze_exit_rules(all_trades)
    exec_quality = analyze_execution_quality(all_orders)
    
    # Generate report
    report_lines = [
        "=" * 80,
        f"SPY PAPER TRADING REPORT",
        f"Analysis Period: {start_date.date()} to {end_date.date()} ({days} days)",
        f"Generated: {datetime.now().isoformat()}",
        "=" * 80,
        "",
        "SUMMARY STATISTICS",
        "-" * 80,
        f"Total Trading Days: {len(set(c['as_of'][:10] for c in all_contexts))}",
        f"Total Contexts: {len(all_contexts)}",
        f"Total Trade Ideas: {len(all_trades)}",
        f"Total Orders: {exec_quality['order_count']}",
        "",
        "STRATEGY DISTRIBUTION",
        "-" * 80,
    ]
    
    for strategy, count in sorted(strategy_dist.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(all_trades) * 100 if all_trades else 0
        report_lines.append(f"  {strategy:30s} {count:5d} ({pct:5.1f}%)")
    
    report_lines.extend([
        "",
        "REGIME CORRELATION",
        "-" * 80,
    ])
    
    for regime, strategies in sorted(regime_corr.items()):
        report_lines.append(f"  {regime}:")
        for strategy, count in sorted(strategies.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"    {strategy:28s} {count:5d}")
    
    report_lines.extend([
        "",
        "RISK METRICS",
        "-" * 80,
        f"  Trade Count:           {risk_metrics['trade_count']:8d}",
        f"  Max Loss (Mean):      ${risk_metrics['max_loss_mean']:8.2f}",
        f"  Max Loss (Min):       ${risk_metrics['max_loss_min']:8.2f}",
        f"  Max Loss (Max):       ${risk_metrics['max_loss_max']:8.2f}",
        f"  Max Profit (Mean):    ${risk_metrics['max_profit_mean']:8.2f}",
        f"  Max Profit (Min):     ${risk_metrics['max_profit_min']:8.2f}",
        f"  Max Profit (Max):     ${risk_metrics['max_profit_max']:8.2f}",
        f"  Breakeven Points:      {risk_metrics['breakeven_count']:8d}",
        "",
        "EXIT RULE CONFIGURATION",
        "-" * 80,
        f"  Profit Target (Mean):  {exit_rules['profit_target_mean']:8.1%}",
        f"  Stop Loss (Mean):      {exit_rules['stop_loss_mean']:8.1%}",
        f"  Trailing Stop (Mean):  {exit_rules['trailing_stop_mean']:8.1%}",
        "",
        "EXECUTION QUALITY",
        "-" * 80,
        f"  Total Orders:          {exec_quality['order_count']:8d}",
        f"  Filled Orders:         {exec_quality.get('filled_count', 0):8d}",
        f"  Rejected Orders:       {exec_quality.get('rejected_count', 0):8d}",
        f"  Fill Rate:             {exec_quality.get('fill_rate', 0):8.1%}",
        f"  Avg Slippage:         ${exec_quality.get('avg_slippage', 0):8.2f}",
        f"  Total Commission:     ${exec_quality.get('total_commission', 0):8.2f}",
        "",
        "=" * 80,
    ])
    
    report = "\n".join(report_lines)
    
    # Save to file if output_dir specified
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / f"spy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\n✓ Report saved to {report_file}")
    
    return report


def main() -> None:
    """Generate and display daily report."""
    parser = argparse.ArgumentParser(description="Generate SPY paper trading report")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include in analysis (default: 30)",
    )
    parser.add_argument(
        "--runs-dir",
        type=str,
        default="runs",
        help="Directory containing run data (default: runs/)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for report file (default: print to stdout)",
    )
    args = parser.parse_args()
    
    runs_dir = Path(args.runs_dir)
    output_dir = Path(args.output) if args.output else None
    
    if not runs_dir.exists():
        print(f"Error: Runs directory not found: {runs_dir}")
        return
    
    report = generate_report(runs_dir, args.days, output_dir)
    print(report)


if __name__ == "__main__":
    from typing import Optional
    main()
