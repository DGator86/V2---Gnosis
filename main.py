from __future__ import annotations

"""Command line entrypoint for Super Gnosis pipeline."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import typer
from dotenv import load_dotenv

from agents.composer.composer_agent_v1 import ComposerAgentV1
from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from config import AppConfig, load_config
from engines.elasticity.elasticity_engine_v1 import ElasticityEngineV1
from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.inputs.market_data_adapter import MarketDataAdapter
from engines.inputs.news_adapter import NewsAdapter
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from engines.inputs.stub_adapters import (
    StaticMarketDataAdapter,
    StaticNewsAdapter,
    StaticOptionsAdapter,
)
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.orchestration.pipeline_runner import PipelineRunner
from engines.sentiment.processors import FlowSentimentProcessor, NewsSentimentProcessor, TechnicalSentimentProcessor
from engines.sentiment.sentiment_engine_v1 import SentimentEngineV1
from ledger.ledger_store import LedgerStore
from trade.trade_agent_v1 import TradeAgentV1

# Load environment variables
load_dotenv()

app = typer.Typer(help="Super Gnosis / DHPE Pipeline CLI")


def build_pipeline(
    symbol: str,
    config: AppConfig,
    adapters: Optional[Dict[str, object]] = None,
) -> PipelineRunner:
    """Assemble a :class:`PipelineRunner` for ``symbol`` using ``config``."""

    adapters = adapters or {}
    options_adapter: OptionsChainAdapter = adapters.get("options") or StaticOptionsAdapter()
    market_adapter: MarketDataAdapter = adapters.get("market") or StaticMarketDataAdapter()
    news_adapter: NewsAdapter = adapters.get("news") or StaticNewsAdapter()

    engines = {
        "hedge": HedgeEngineV3(options_adapter, config.engines.hedge.model_dump()),
        "liquidity": LiquidityEngineV1(market_adapter, config.engines.liquidity.model_dump()),
        "sentiment": SentimentEngineV1(
            [
                NewsSentimentProcessor(news_adapter, config.engines.sentiment.model_dump()),
                FlowSentimentProcessor(config.engines.sentiment.model_dump()),
                TechnicalSentimentProcessor(market_adapter, config.engines.sentiment.model_dump()),
            ],
            config.engines.sentiment.model_dump(),
        ),
        "elasticity": ElasticityEngineV1(market_adapter, config.engines.elasticity.model_dump()),
    }

    primary_agents = {
        "primary_hedge": HedgeAgentV3(config.agents.hedge.model_dump()),
        "primary_liquidity": LiquidityAgentV1(config.agents.liquidity.model_dump()),
        "primary_sentiment": SentimentAgentV1(config.agents.sentiment.model_dump()),
    }

    composer = ComposerAgentV1(
        config.agents.composer.weights,
        config.agents.composer.model_dump(),
    )
    trade_agent = TradeAgentV1(options_adapter, config.agents.trade.model_dump())

    ledger_path = Path(config.tracking.ledger_path)
    ledger_store = LedgerStore(ledger_path)

    return PipelineRunner(
        symbol=symbol,
        engines=engines,
        primary_agents=primary_agents,
        composer=composer,
        trade_agent=trade_agent,
        ledger_store=ledger_store,
        config=config.model_dump(),
    )


@app.command()
def run_once(
    symbol: str = typer.Option("SPY", help="Ticker symbol to evaluate."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run mode (no actual execution)"),
) -> None:
    """Run a single pipeline iteration for ``symbol`` and print the results."""
    
    config = load_config()
    runner = build_pipeline(symbol, config)
    now = datetime.now(timezone.utc)
    result = runner.run_once(now)
    
    if dry_run:
        typer.echo("🔍 DRY-RUN MODE: No orders will be executed")
    
    typer.echo(result)


@app.command()
def live_loop(
    symbol: str = typer.Option("SPY", help="Ticker symbol to trade."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run mode (no actual execution)"),
    interval: int = typer.Option(60, "--interval", help="Loop interval in seconds (default: 60)"),
) -> None:
    """
    Run autonomous trading loop with continuous execution.
    
    This command starts the autonomous trading system that:
    1. Runs the full pipeline every {interval} seconds
    2. Generates trade ideas based on current market conditions
    3. Executes trades on Alpaca Paper (if --dry-run not specified)
    4. Tracks predictions and learns from outcomes
    5. Self-optimizes based on performance
    
    Example:
        # Dry-run to preview without execution
        python main.py live-loop --symbol SPY --dry-run
        
        # Start live paper trading
        python main.py live-loop --symbol SPY
        
        # Custom interval (5 minutes)
        python main.py live-loop --symbol SPY --interval 300
    """
    from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
    
    config = load_config()
    
    # Initialize broker (Alpaca Paper)
    broker = None
    if not dry_run:
        try:
            typer.echo("🔌 Connecting to Alpaca Paper Trading...")
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            typer.echo(f"✅ Connected to Alpaca Paper Trading")
            typer.echo(f"   Account: {account.account_id}")
            typer.echo(f"   Cash: ${account.cash:,.2f}")
            typer.echo(f"   Buying Power: ${account.buying_power:,.2f}")
            typer.echo(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
        except Exception as e:
            typer.echo(f"❌ Failed to connect to Alpaca: {e}", err=True)
            typer.echo("   Make sure ALPACA_API_KEY and ALPACA_SECRET_KEY are set in .env", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("🔍 DRY-RUN MODE: No actual execution")
    
    # Build pipeline with broker
    adapters = {}
    if broker:
        adapters["broker"] = broker
    
    runner = build_pipeline(symbol, config, adapters)
    
    typer.echo("\n" + "="*80)
    typer.echo("🚀 AUTONOMOUS TRADING LOOP STARTED")
    typer.echo("="*80)
    typer.echo(f"   Symbol: {symbol}")
    typer.echo(f"   Mode: {'DRY-RUN' if dry_run else 'LIVE PAPER TRADING'}")
    typer.echo(f"   Interval: {interval} seconds")
    typer.echo(f"   Press Ctrl+C to stop")
    typer.echo("="*80 + "\n")
    
    iteration = 0
    try:
        while True:
            iteration += 1
            now = datetime.now(timezone.utc)
            
            typer.echo(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Iteration #{iteration}")
            typer.echo("-" * 80)
            
            try:
                # Run pipeline
                result = runner.run_once(now)
                
                # Report results
                if hasattr(result, 'trade_ideas'):
                    n_ideas = len(result.trade_ideas) if result.trade_ideas else 0
                    typer.echo(f"   ✓ Generated {n_ideas} trade ideas")
                    
                    # Show top trade idea
                    if n_ideas > 0 and not dry_run:
                        top_idea = result.trade_ideas[0]
                        typer.echo(f"   🎯 Top Idea: {top_idea.strategy_type.value if hasattr(top_idea, 'strategy_type') else 'N/A'}")
                        typer.echo(f"      Confidence: {top_idea.confidence:.2%}" if hasattr(top_idea, 'confidence') else "")
                
                if hasattr(result, 'order_results') and result.order_results:
                    n_orders = len(result.order_results)
                    typer.echo(f"   📊 Executed {n_orders} orders")
                    for order in result.order_results:
                        status = order.status.value if hasattr(order.status, 'value') else order.status
                        typer.echo(f"      {order.symbol}: {status}")
                
                # Check account if live
                if broker and not dry_run:
                    account = broker.get_account()
                    typer.echo(f"   💰 Portfolio: ${account.portfolio_value:,.2f} | Cash: ${account.cash:,.2f}")
                
            except Exception as e:
                typer.echo(f"   ❌ Error in iteration: {e}", err=True)
            
            # Wait for next iteration
            typer.echo(f"   ⏳ Next iteration in {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        typer.echo("\n\n" + "="*80)
        typer.echo("🛑 AUTONOMOUS TRADING LOOP STOPPED")
        typer.echo("="*80)
        typer.echo(f"   Total Iterations: {iteration}")
        
        if broker and not dry_run:
            try:
                account = broker.get_account()
                typer.echo(f"\n   Final Portfolio Value: ${account.portfolio_value:,.2f}")
                typer.echo(f"   Final Cash: ${account.cash:,.2f}")
                positions = broker.get_positions()
                typer.echo(f"   Open Positions: {len(positions)}")
            except:
                pass
        
        typer.echo("="*80)


if __name__ == "__main__":
    app()
