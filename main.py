"""
DHPE (Dealer Hedge Positioning Engine) Pipeline
Main entry point

Flow:
  Inputs → Engines (Hedge/Volume/Sentiment) → Standardization → Primary Agents → Composer → Tracking → Feedback

Usage:
    python main.py                          # Single run
    python main.py --backtest --runs 50     # Backtest mode
    python main.py --symbol QQQ             # Different symbol
"""
import argparse
import json
from engines.orchestration.pipeline_runner import PipelineRunner
from engines.orchestration.logger import get_logger

logger = get_logger('dhpe.main')


def main():
    parser = argparse.ArgumentParser(description='DHPE Pipeline Runner')
    parser.add_argument('--symbol', type=str, default='SPY', help='Trading symbol')
    parser.add_argument('--backtest', action='store_true', help='Run backtest mode')
    parser.add_argument('--runs', type=int, default=10, help='Number of backtest runs')
    parser.add_argument('--config', type=str, default=None, help='Path to config.yaml')
    
    args = parser.parse_args()
    
    logger.info(f"Starting DHPE Pipeline (symbol={args.symbol})")
    
    # Initialize pipeline
    pipeline = PipelineRunner(config_path=args.config)
    
    if args.backtest:
        # Backtest mode
        logger.info(f"Running backtest: {args.runs} iterations")
        result = pipeline.run_backtest(args.symbol, num_runs=args.runs)
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        print(f"Symbol: {result['symbol']}")
        print(f"Total runs: {result['num_runs']}")
        print(f"\nAggregate Metrics:")
        for key, value in result['aggregate_metrics'].items():
            print(f"  {key}: {value}")
        print(f"\nLearning Summary:")
        print(f"  Best agent: {result['learning_summary'].get('best_agent', 'N/A')}")
        print(f"  Agent scores:")
        for agent, score in result['learning_summary'].get('agent_scores', {}).items():
            print(f"    {agent}: {score:.4f}")
        print("="*60 + "\n")
    
    else:
        # Single run mode
        result = pipeline.run_single_symbol(args.symbol)
        
        print("\n" + "="*60)
        print("SINGLE RUN RESULT")
        print("="*60)
        print(f"Run ID: {result['run_id']}")
        print(f"Symbol: {result['symbol']}")
        print(f"Regime: {result['snapshot'].regime}")
        print(f"\nPrimary Suggestions:")
        for sug in result['primary_suggestions']:
            print(f"  {sug.layer}: {sug.action} (conf={sug.confidence:.2f})")
        print(f"\nComposed Suggestion:")
        comp = result['composed_suggestion']
        print(f"  Action: {comp.action}")
        print(f"  Confidence: {comp.confidence:.2f}")
        print(f"  Reasoning: {comp.reasoning}")
        
        if result['position']:
            pos = result['position']
            print(f"\nPosition Opened:")
            print(f"  Side: {pos.side}")
            print(f"  Entry: ${pos.entry_price:.2f}")
            print(f"  Strategy: {pos.strategy_type}")
        
        if result['result']:
            res = result['result']
            print(f"\nPosition Closed:")
            print(f"  Exit: ${res.exit_price:.2f}")
            print(f"  P&L: ${res.pnl:.2f} ({res.pnl_pct:.2%})")
        
        print("="*60 + "\n")
    
    logger.info("DHPE Pipeline completed")


if __name__ == "__main__":
    main()
