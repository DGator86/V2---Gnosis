#!/usr/bin/env python3
"""
Daily SPY Paper Trading Script

Runs full pipeline for SPY in paper mode and persists results.

Usage:
    python scripts/run_daily_spy_paper.py
    python scripts/run_daily_spy_paper.py --execute  # Actually execute trades in simulated broker
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from pipeline.full_pipeline import (
    build_default_pipeline_components,
    run_full_pipeline_for_symbol,
)


def serialize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize pipeline result for JSON persistence.
    
    Converts Pydantic models and datetime objects to JSON-serializable format.
    """
    serialized = {
        "symbol": result["symbol"],
        "as_of": result["as_of"].isoformat(),
        "composer_context": result["composer_context"].model_dump() if hasattr(result["composer_context"], "model_dump") else str(result["composer_context"]),
        "trade_ideas": [
            idea.model_dump() if hasattr(idea, "model_dump") else str(idea)
            for idea in result["trade_ideas"]
        ],
        "order_results": [
            order.model_dump() if hasattr(order, "model_dump") else str(order)
            for order in result["order_results"]
        ],
        "hyperparams": result.get("hyperparams", {}),
    }
    return serialized


def persist_results(result: Dict[str, Any], output_dir: Path) -> None:
    """
    Persist pipeline results to disk.
    
    Creates JSONL files for:
        - Context: composer context and market state
        - Trades: trade ideas with ranking and risk metrics
        - Orders: execution results (if executed)
    
    Args:
        result: Pipeline result dictionary
        output_dir: Output directory (e.g., runs/2025-01-15/)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    serialized = serialize_result(result)
    
    # Write context
    context_file = output_dir / f"{result['symbol']}_context.jsonl"
    with open(context_file, "a") as f:
        context_entry = {
            "as_of": serialized["as_of"],
            "symbol": serialized["symbol"],
            "context": serialized["composer_context"],
            "hyperparams": serialized["hyperparams"],
        }
        f.write(json.dumps(context_entry) + "\n")
    
    # Write trades
    trades_file = output_dir / f"{result['symbol']}_trades.jsonl"
    with open(trades_file, "a") as f:
        for trade in serialized["trade_ideas"]:
            trade_entry = {
                "as_of": serialized["as_of"],
                "symbol": serialized["symbol"],
                "trade": trade,
            }
            f.write(json.dumps(trade_entry) + "\n")
    
    # Write orders (if any)
    if serialized["order_results"]:
        orders_file = output_dir / f"{result['symbol']}_orders.jsonl"
        with open(orders_file, "a") as f:
            for order in serialized["order_results"]:
                order_entry = {
                    "as_of": serialized["as_of"],
                    "symbol": serialized["symbol"],
                    "order": order,
                }
                f.write(json.dumps(order_entry) + "\n")
    
    print(f"✓ Persisted results to {output_dir}")


def main() -> None:
    """Run SPY paper trading pipeline."""
    parser = argparse.ArgumentParser(description="Run daily SPY paper trading")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute trades in simulated broker (default: dry-run only)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="runs",
        help="Output directory for results (default: runs/)",
    )
    parser.add_argument(
        "--underlying-price",
        type=float,
        default=None,
        help="Override underlying price (default: 450.0)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
        help="Capital allocation (default: 100,000)",
    )
    args = parser.parse_args()
    
    # Build components
    print("Building pipeline components...")
    components = build_default_pipeline_components()
    
    # Run pipeline
    as_of = datetime.utcnow()
    print(f"Running SPY pipeline at {as_of.isoformat()}...")
    
    result = run_full_pipeline_for_symbol(
        symbol="SPY",
        as_of=as_of,
        components=components,
        mode="paper",
        execute=args.execute,
        underlying_price=args.underlying_price,
        capital=args.capital,
    )
    
    # Report
    n_ideas = len(result["trade_ideas"])
    n_orders = len(result["order_results"])
    print(f"✓ Generated {n_ideas} trade ideas")
    if args.execute:
        print(f"✓ Executed {n_orders} orders")
    
    # Persist
    date_str = as_of.strftime("%Y-%m-%d")
    output_dir = Path(args.output_dir) / date_str
    persist_results(result, output_dir)
    
    print(f"\n{'='*60}")
    print(f"SPY Paper Trading Complete")
    print(f"{'='*60}")
    print(f"Date: {date_str}")
    print(f"Trade Ideas: {n_ideas}")
    print(f"Orders Executed: {n_orders}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
