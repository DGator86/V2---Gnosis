#!/usr/bin/env python3
"""
Regime Correlation Analyzer for Phase 3 Paper Trading

Performs deep analysis of regime → strategy → outcome mappings to validate
that strategy selection adapts appropriately to market conditions.

Usage:
    python scripts/analysis/regime_correlation.py
    python scripts/analysis/regime_correlation.py --runs-dir runs --days 14
    python scripts/analysis/regime_correlation.py --output regime_analysis.txt
"""

import argparse
import json
from collections import defaultdict
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


def collect_data(runs_dir: Path, days: int) -> Dict[str, List]:
    """Collect contexts and trades from runs within specified days."""
    cutoff_date = datetime.now() - timedelta(days=days)
    contexts = []
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
        
        # Load contexts
        context_file = day_dir / "SPY_context.jsonl"
        if context_file.exists():
            contexts.extend(load_jsonl(context_file))
        
        # Load trades
        trades_file = day_dir / "SPY_trades.jsonl"
        if trades_file.exists():
            trades.extend(load_jsonl(trades_file))
    
    return {"contexts": contexts, "trades": trades}


def analyze_regime_dimensions(contexts: List[Dict]) -> Dict[str, Any]:
    """Analyze individual regime dimensions (volatility, direction, confidence)."""
    vol_regimes = [ctx["context"]["volatility_regime"] for ctx in contexts]
    directions = [ctx["context"]["direction"] for ctx in contexts]
    confidences = [ctx["context"]["confidence"] for ctx in contexts]
    elastic_energies = [ctx["context"].get("elastic_energy", 0.0) for ctx in contexts]
    
    return {
        "volatility_regimes": dict(zip(*zip(*[(v, vol_regimes.count(v)) for v in set(vol_regimes)]))),
        "directions": dict(zip(*zip(*[(d, directions.count(d)) for d in set(directions)]))),
        "confidence_stats": {
            "mean": sum(confidences) / len(confidences) if confidences else 0,
            "min": min(confidences) if confidences else 0,
            "max": max(confidences) if confidences else 0,
        },
        "elastic_energy_stats": {
            "mean": sum(elastic_energies) / len(elastic_energies) if elastic_energies else 0,
            "min": min(elastic_energies) if elastic_energies else 0,
            "max": max(elastic_energies) if elastic_energies else 0,
        },
    }


def analyze_strategy_by_regime(contexts: List[Dict], trades: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Build regime key → strategy distribution mapping."""
    regime_strategies = defaultdict(list)
    
    # Match contexts to trades (assuming temporal ordering)
    for ctx, trade_batch in zip(contexts, trades):
        vol_regime = ctx["context"]["volatility_regime"]
        direction = ctx["context"]["direction"]
        regime_key = f"{vol_regime}_{direction}"
        
        # Extract strategy from trade
        strategy = trade_batch["trade"]["strategy_type"]
        regime_strategies[regime_key].append(strategy)
    
    # Convert to counts
    return {
        regime: dict(zip(*zip(*[(s, strategies.count(s)) for s in set(strategies)])))
        for regime, strategies in regime_strategies.items()
    }


def analyze_risk_profile_by_regime(contexts: List[Dict], trades: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Analyze risk metrics (max loss, max profit, Greeks) grouped by regime."""
    regime_risks = defaultdict(lambda: {"max_losses": [], "max_profits": [], "deltas": [], "vegas": []})
    
    for ctx, trade_batch in zip(contexts, trades):
        vol_regime = ctx["context"]["volatility_regime"]
        direction = ctx["context"]["direction"]
        regime_key = f"{vol_regime}_{direction}"
        
        trade = trade_batch["trade"]
        regime_risks[regime_key]["max_losses"].append(trade.get("max_loss", 0.0))
        regime_risks[regime_key]["max_profits"].append(trade.get("max_profit", 0.0))
        regime_risks[regime_key]["deltas"].append(trade.get("greeks_at_entry", {}).get("delta", 0.0))
        regime_risks[regime_key]["vegas"].append(trade.get("greeks_at_entry", {}).get("vega", 0.0))
    
    # Compute stats
    result = {}
    for regime_key, metrics in regime_risks.items():
        result[regime_key] = {
            "avg_max_loss": sum(metrics["max_losses"]) / len(metrics["max_losses"]) if metrics["max_losses"] else 0,
            "avg_max_profit": sum(metrics["max_profits"]) / len(metrics["max_profits"]) if metrics["max_profits"] else 0,
            "avg_delta": sum(metrics["deltas"]) / len(metrics["deltas"]) if metrics["deltas"] else 0,
            "avg_vega": sum(metrics["vegas"]) / len(metrics["vegas"]) if metrics["vegas"] else 0,
            "trade_count": len(metrics["max_losses"]),
        }
    
    return result


def analyze_confidence_impact(contexts: List[Dict], trades: List[Dict]) -> Dict[str, Any]:
    """Analyze how confidence levels correlate with risk sizing and strategy selection."""
    confidence_buckets = defaultdict(lambda: {"strategies": [], "max_losses": [], "max_profits": []})
    
    for ctx, trade_batch in zip(contexts, trades):
        confidence = ctx["context"]["confidence"]
        
        # Bucket confidence into low/medium/high
        if confidence < 0.5:
            bucket = "low_confidence"
        elif confidence < 0.75:
            bucket = "medium_confidence"
        else:
            bucket = "high_confidence"
        
        trade = trade_batch["trade"]
        confidence_buckets[bucket]["strategies"].append(trade["strategy_type"])
        confidence_buckets[bucket]["max_losses"].append(trade.get("max_loss", 0.0))
        confidence_buckets[bucket]["max_profits"].append(trade.get("max_profit", 0.0))
    
    # Compute stats
    result = {}
    for bucket, data in confidence_buckets.items():
        result[bucket] = {
            "strategy_distribution": dict(zip(*zip(*[(s, data["strategies"].count(s)) for s in set(data["strategies"])]))),
            "avg_max_loss": sum(data["max_losses"]) / len(data["max_losses"]) if data["max_losses"] else 0,
            "avg_max_profit": sum(data["max_profits"]) / len(data["max_profits"]) if data["max_profits"] else 0,
            "trade_count": len(data["strategies"]),
        }
    
    return result


def generate_report(runs_dir: Path, days: int = 30, output_path: Optional[Path] = None) -> str:
    """Generate comprehensive regime correlation report."""
    data = collect_data(runs_dir, days)
    contexts = data["contexts"]
    trades = data["trades"]
    
    if not contexts or not trades:
        return "No data available for analysis."
    
    # Run analyses
    regime_dims = analyze_regime_dimensions(contexts)
    strategy_by_regime = analyze_strategy_by_regime(contexts, trades)
    risk_by_regime = analyze_risk_profile_by_regime(contexts, trades)
    confidence_impact = analyze_confidence_impact(contexts, trades)
    
    # Build report
    cutoff = datetime.now() - timedelta(days=days)
    lines = [
        "=" * 80,
        "REGIME CORRELATION ANALYSIS",
        f"Analysis Period: {cutoff.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')} ({days} days)",
        f"Generated: {datetime.now().isoformat()}",
        "=" * 80,
        "",
        "REGIME DIMENSIONS",
        "-" * 80,
    ]
    
    # Volatility regimes
    lines.append("Volatility Regimes:")
    for regime, count in sorted(regime_dims["volatility_regimes"].items()):
        pct = 100 * count / len(contexts)
        lines.append(f"  {regime:20s} {count:3d} ({pct:5.1f}%)")
    
    lines.append("")
    lines.append("Directional Bias:")
    for direction, count in sorted(regime_dims["directions"].items()):
        pct = 100 * count / len(contexts)
        lines.append(f"  {direction:20s} {count:3d} ({pct:5.1f}%)")
    
    lines.append("")
    conf_stats = regime_dims["confidence_stats"]
    lines.append("Confidence Statistics:")
    lines.append(f"  Mean: {conf_stats['mean']:.3f}")
    lines.append(f"  Min:  {conf_stats['min']:.3f}")
    lines.append(f"  Max:  {conf_stats['max']:.3f}")
    
    lines.append("")
    ee_stats = regime_dims["elastic_energy_stats"]
    lines.append("Elastic Energy Statistics:")
    lines.append(f"  Mean: {ee_stats['mean']:.3f}")
    lines.append(f"  Min:  {ee_stats['min']:.3f}")
    lines.append(f"  Max:  {ee_stats['max']:.3f}")
    
    # Strategy by regime
    lines.append("")
    lines.append("STRATEGY SELECTION BY REGIME")
    lines.append("-" * 80)
    for regime_key in sorted(strategy_by_regime.keys()):
        lines.append(f"{regime_key}:")
        for strategy, count in sorted(strategy_by_regime[regime_key].items(), key=lambda x: -x[1]):
            lines.append(f"  {strategy:30s} {count:3d}")
        lines.append("")
    
    # Risk profile by regime
    lines.append("RISK PROFILE BY REGIME")
    lines.append("-" * 80)
    for regime_key in sorted(risk_by_regime.keys()):
        risk = risk_by_regime[regime_key]
        lines.append(f"{regime_key}:")
        lines.append(f"  Trade Count:       {risk['trade_count']:3d}")
        lines.append(f"  Avg Max Loss:      $ {risk['avg_max_loss']:8.2f}")
        lines.append(f"  Avg Max Profit:    $ {risk['avg_max_profit']:8.2f}")
        lines.append(f"  Avg Delta:           {risk['avg_delta']:6.3f}")
        lines.append(f"  Avg Vega:            {risk['avg_vega']:6.3f}")
        lines.append("")
    
    # Confidence impact
    lines.append("CONFIDENCE IMPACT ANALYSIS")
    lines.append("-" * 80)
    for bucket in ["low_confidence", "medium_confidence", "high_confidence"]:
        if bucket not in confidence_impact:
            continue
        impact = confidence_impact[bucket]
        lines.append(f"{bucket.replace('_', ' ').title()}:")
        lines.append(f"  Trade Count:       {impact['trade_count']:3d}")
        lines.append(f"  Avg Max Loss:      $ {impact['avg_max_loss']:8.2f}")
        lines.append(f"  Avg Max Profit:    $ {impact['avg_max_profit']:8.2f}")
        lines.append("  Strategy Distribution:")
        for strategy, count in sorted(impact["strategy_distribution"].items(), key=lambda x: -x[1]):
            lines.append(f"    {strategy:28s} {count:3d}")
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
    parser = argparse.ArgumentParser(description="Analyze regime correlation in paper trading runs")
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
