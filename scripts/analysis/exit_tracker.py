#!/usr/bin/env python3
"""
Exit Trigger Tracker for Phase 3 Paper Trading

Analyzes exit rule configuration and simulates which triggers would fire
under different market scenarios to validate exit management robustness.

Usage:
    python scripts/analysis/exit_tracker.py
    python scripts/analysis/exit_tracker.py --runs-dir runs --days 14
    python scripts/analysis/exit_tracker.py --output exit_analysis.txt
"""

import argparse
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file into list of dictionaries."""
    results = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def collect_trades(runs_dir: Path, days: int) -> List[Dict]:
    """Collect trades from runs within specified days."""
    cutoff_date = datetime.now() - timedelta(days=days)
    trades = []
    
    for day_dir in sorted(runs_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        
        try:
            day_date = datetime.strptime(day_dir.name, "%Y-%m-%d")
            if day_date < cutoff_date:
                continue
        except ValueError:
            continue
        
        trades_file = day_dir / "SPY_trades.jsonl"
        if trades_file.exists():
            trades.extend(load_jsonl(trades_file))
    
    return trades


def analyze_exit_rule_distribution(trades: List[Dict]) -> Dict[str, Any]:
    """Analyze distribution of exit rule parameters across all trades."""
    profit_targets = []
    stop_losses = []
    trailing_stops = []
    time_stops = []
    greek_stops = []
    
    for trade_batch in trades:
        trade = trade_batch["trade"]
        exit_rules = trade.get("exit_rules", {})
        
        if "profit_target_pct" in exit_rules:
            profit_targets.append(exit_rules["profit_target_pct"])
        if "stop_loss_pct" in exit_rules:
            stop_losses.append(exit_rules["stop_loss_pct"])
        if "trailing_stop_pct" in exit_rules:
            trailing_stops.append(exit_rules["trailing_stop_pct"])
        if "time_stop_days" in exit_rules:
            time_stops.append(exit_rules["time_stop_days"])
        if "delta_exit_threshold" in exit_rules:
            greek_stops.append(exit_rules["delta_exit_threshold"])
    
    return {
        "profit_target": {
            "count": len(profit_targets),
            "mean": sum(profit_targets) / len(profit_targets) if profit_targets else 0,
            "min": min(profit_targets) if profit_targets else 0,
            "max": max(profit_targets) if profit_targets else 0,
            "distribution": dict(Counter(profit_targets)),
        },
        "stop_loss": {
            "count": len(stop_losses),
            "mean": sum(stop_losses) / len(stop_losses) if stop_losses else 0,
            "min": min(stop_losses) if stop_losses else 0,
            "max": max(stop_losses) if stop_losses else 0,
            "distribution": dict(Counter(stop_losses)),
        },
        "trailing_stop": {
            "count": len(trailing_stops),
            "mean": sum(trailing_stops) / len(trailing_stops) if trailing_stops else 0,
            "min": min(trailing_stops) if trailing_stops else 0,
            "max": max(trailing_stops) if trailing_stops else 0,
            "distribution": dict(Counter(trailing_stops)),
        },
        "time_stop": {
            "count": len(time_stops),
            "mean": sum(time_stops) / len(time_stops) if time_stops else 0,
            "min": min(time_stops) if time_stops else 0,
            "max": max(time_stops) if time_stops else 0,
            "distribution": dict(Counter(time_stops)),
        },
        "greek_stop": {
            "count": len(greek_stops),
            "mean": sum(greek_stops) / len(greek_stops) if greek_stops else 0,
            "min": min(greek_stops) if greek_stops else 0,
            "max": max(greek_stops) if greek_stops else 0,
            "distribution": dict(Counter(greek_stops)),
        },
    }


def analyze_exit_rule_completeness(trades: List[Dict]) -> Dict[str, Any]:
    """Analyze which trades have which exit rules configured."""
    rule_presence = defaultdict(int)
    rule_combinations = defaultdict(int)
    
    for trade_batch in trades:
        trade = trade_batch["trade"]
        exit_rules = trade.get("exit_rules", {})
        
        # Track individual rule presence
        present_rules = []
        if "profit_target_pct" in exit_rules:
            rule_presence["profit_target"] += 1
            present_rules.append("profit_target")
        if "stop_loss_pct" in exit_rules:
            rule_presence["stop_loss"] += 1
            present_rules.append("stop_loss")
        if "trailing_stop_pct" in exit_rules:
            rule_presence["trailing_stop"] += 1
            present_rules.append("trailing_stop")
        if "time_stop_days" in exit_rules:
            rule_presence["time_stop"] += 1
            present_rules.append("time_stop")
        if "delta_exit_threshold" in exit_rules:
            rule_presence["greek_stop"] += 1
            present_rules.append("greek_stop")
        
        # Track combinations
        combo_key = "+".join(sorted(present_rules)) if present_rules else "none"
        rule_combinations[combo_key] += 1
    
    total_trades = len(trades)
    return {
        "rule_presence": {
            rule: {"count": count, "pct": 100 * count / total_trades}
            for rule, count in rule_presence.items()
        },
        "rule_combinations": dict(rule_combinations),
        "total_trades": total_trades,
    }


def simulate_exit_triggers(trades: List[Dict]) -> Dict[str, Any]:
    """Simulate which exit triggers would fire under various scenarios."""
    scenarios = {
        "fast_profit": {"pnl_change": +0.40, "time_elapsed": 1, "delta_change": -0.10},  # +40% quick win
        "slow_profit": {"pnl_change": +0.20, "time_elapsed": 25, "delta_change": -0.05},  # +20% slow win
        "fast_loss": {"pnl_change": -0.30, "time_elapsed": 1, "delta_change": +0.15},  # -30% quick loss
        "slow_loss": {"pnl_change": -0.20, "time_elapsed": 25, "delta_change": +0.10},  # -20% slow loss
        "choppy": {"pnl_change": +0.10, "time_elapsed": 15, "delta_change": 0.0},  # +10% choppy
    }
    
    results = defaultdict(lambda: defaultdict(int))
    
    for scenario_name, scenario_params in scenarios.items():
        for trade_batch in trades:
            trade = trade_batch["trade"]
            exit_rules = trade.get("exit_rules", {})
            
            # Check each trigger
            triggered = []
            
            # Profit target
            if "profit_target_pct" in exit_rules:
                if scenario_params["pnl_change"] >= exit_rules["profit_target_pct"]:
                    triggered.append("profit_target")
            
            # Stop loss
            if "stop_loss_pct" in exit_rules:
                if scenario_params["pnl_change"] <= -exit_rules["stop_loss_pct"]:
                    triggered.append("stop_loss")
            
            # Trailing stop (simplified: assume trailing stop fires if profit taken back)
            if "trailing_stop_pct" in exit_rules:
                if scenario_params["pnl_change"] > 0:
                    # Assume we had profit, now checking if it retraced
                    if scenario_params["pnl_change"] < exit_rules["trailing_stop_pct"]:
                        triggered.append("trailing_stop")
            
            # Time stop
            if "time_stop_days" in exit_rules:
                if scenario_params["time_elapsed"] >= exit_rules["time_stop_days"]:
                    triggered.append("time_stop")
            
            # Greek stop
            if "delta_exit_threshold" in exit_rules:
                initial_delta = trade.get("greeks_at_entry", {}).get("delta", 0.5)
                final_delta = initial_delta + scenario_params["delta_change"]
                if abs(final_delta) < exit_rules["delta_exit_threshold"]:
                    triggered.append("greek_stop")
            
            # Record results
            if triggered:
                # Record first trigger (priority order)
                first_trigger = triggered[0]
                results[scenario_name][first_trigger] += 1
                results[scenario_name]["total"] += 1
            else:
                results[scenario_name]["no_trigger"] += 1
    
    return dict(results)


def analyze_exit_rule_by_strategy(trades: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """Analyze exit rule usage grouped by strategy type."""
    strategy_exit_rules = defaultdict(lambda: {
        "profit_targets": [],
        "stop_losses": [],
        "trailing_stops": [],
        "time_stops": [],
        "greek_stops": [],
        "count": 0,
    })
    
    for trade_batch in trades:
        trade = trade_batch["trade"]
        strategy = trade["strategy_type"]
        exit_rules = trade.get("exit_rules", {})
        
        strategy_exit_rules[strategy]["count"] += 1
        
        if "profit_target_pct" in exit_rules:
            strategy_exit_rules[strategy]["profit_targets"].append(exit_rules["profit_target_pct"])
        if "stop_loss_pct" in exit_rules:
            strategy_exit_rules[strategy]["stop_losses"].append(exit_rules["stop_loss_pct"])
        if "trailing_stop_pct" in exit_rules:
            strategy_exit_rules[strategy]["trailing_stops"].append(exit_rules["trailing_stop_pct"])
        if "time_stop_days" in exit_rules:
            strategy_exit_rules[strategy]["time_stops"].append(exit_rules["time_stop_days"])
        if "delta_exit_threshold" in exit_rules:
            strategy_exit_rules[strategy]["greek_stops"].append(exit_rules["delta_exit_threshold"])
    
    # Compute averages
    result = {}
    for strategy, data in strategy_exit_rules.items():
        result[strategy] = {
            "count": data["count"],
            "avg_profit_target": sum(data["profit_targets"]) / len(data["profit_targets"]) if data["profit_targets"] else None,
            "avg_stop_loss": sum(data["stop_losses"]) / len(data["stop_losses"]) if data["stop_losses"] else None,
            "avg_trailing_stop": sum(data["trailing_stops"]) / len(data["trailing_stops"]) if data["trailing_stops"] else None,
            "avg_time_stop": sum(data["time_stops"]) / len(data["time_stops"]) if data["time_stops"] else None,
            "avg_greek_stop": sum(data["greek_stops"]) / len(data["greek_stops"]) if data["greek_stops"] else None,
        }
    
    return result


def generate_report(runs_dir: Path, days: int = 30, output_path: Optional[Path] = None) -> str:
    """Generate comprehensive exit trigger analysis report."""
    trades = collect_trades(runs_dir, days)
    
    if not trades:
        return "No trade data available for analysis."
    
    # Run analyses
    exit_dist = analyze_exit_rule_distribution(trades)
    exit_completeness = analyze_exit_rule_completeness(trades)
    exit_simulation = simulate_exit_triggers(trades)
    exit_by_strategy = analyze_exit_rule_by_strategy(trades)
    
    # Build report
    cutoff = datetime.now() - timedelta(days=days)
    lines = [
        "=" * 80,
        "EXIT TRIGGER ANALYSIS",
        f"Analysis Period: {cutoff.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')} ({days} days)",
        f"Generated: {datetime.now().isoformat()}",
        "=" * 80,
        "",
        "EXIT RULE DISTRIBUTION",
        "-" * 80,
    ]
    
    for rule_name, stats in exit_dist.items():
        lines.append(f"{rule_name.upper().replace('_', ' ')}:")
        lines.append(f"  Configured in: {stats['count']:3d} trades")
        if stats['count'] > 0:
            lines.append(f"  Mean:          {stats['mean']:6.1f}")
            lines.append(f"  Min:           {stats['min']:6.1f}")
            lines.append(f"  Max:           {stats['max']:6.1f}")
        lines.append("")
    
    # Exit rule completeness
    lines.append("EXIT RULE COMPLETENESS")
    lines.append("-" * 80)
    lines.append(f"Total Trades Analyzed: {exit_completeness['total_trades']}")
    lines.append("")
    lines.append("Rule Presence:")
    for rule, data in sorted(exit_completeness["rule_presence"].items()):
        lines.append(f"  {rule:20s} {data['count']:3d} ({data['pct']:5.1f}%)")
    
    lines.append("")
    lines.append("Rule Combinations:")
    for combo, count in sorted(exit_completeness["rule_combinations"].items(), key=lambda x: -x[1]):
        pct = 100 * count / exit_completeness['total_trades']
        lines.append(f"  {combo:50s} {count:3d} ({pct:5.1f}%)")
    
    # Simulated triggers
    lines.append("")
    lines.append("SIMULATED TRIGGER ANALYSIS")
    lines.append("-" * 80)
    lines.append("This section simulates which exit triggers would fire under different")
    lines.append("market scenarios to validate exit management robustness.")
    lines.append("")
    
    for scenario, triggers in sorted(exit_simulation.items()):
        lines.append(f"{scenario.upper().replace('_', ' ')} SCENARIO:")
        total = triggers.get("total", 0)
        for trigger, count in sorted(triggers.items()):
            if trigger == "total":
                continue
            pct = 100 * count / len(trades) if len(trades) > 0 else 0
            lines.append(f"  {trigger:20s} {count:3d} ({pct:5.1f}% of all trades)")
        if "no_trigger" in triggers:
            pct = 100 * triggers["no_trigger"] / len(trades)
            lines.append(f"  {'no_trigger':20s} {triggers['no_trigger']:3d} ({pct:5.1f}% of all trades)")
        lines.append("")
    
    # Exit rules by strategy
    lines.append("EXIT RULES BY STRATEGY")
    lines.append("-" * 80)
    for strategy, rules in sorted(exit_by_strategy.items()):
        lines.append(f"{strategy}:")
        lines.append(f"  Trade Count:       {rules['count']:3d}")
        if rules["avg_profit_target"] is not None:
            lines.append(f"  Avg Profit Target: {rules['avg_profit_target']:6.1f}%")
        if rules["avg_stop_loss"] is not None:
            lines.append(f"  Avg Stop Loss:     {rules['avg_stop_loss']:6.1f}%")
        if rules["avg_trailing_stop"] is not None:
            lines.append(f"  Avg Trailing Stop: {rules['avg_trailing_stop']:6.1f}%")
        if rules["avg_time_stop"] is not None:
            lines.append(f"  Avg Time Stop:     {rules['avg_time_stop']:6.1f} days")
        if rules["avg_greek_stop"] is not None:
            lines.append(f"  Avg Greek Stop:    {rules['avg_greek_stop']:6.3f}")
        lines.append("")
    
    lines.append("=" * 80)
    
    report = "\n".join(lines)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)
        print(f"Report saved to {output_path}")
    
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze exit triggers in paper trading runs")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory containing daily run folders (default: runs/)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: print to stdout)",
    )
    
    args = parser.parse_args()
    
    report = generate_report(args.runs_dir, args.days, args.output)
    if not args.output:
        print(report)


if __name__ == "__main__":
    main()
