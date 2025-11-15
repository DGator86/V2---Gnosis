from __future__ import annotations

"""Command line entrypoint for Super Gnosis pipeline."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import typer

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
def run_once(symbol: str = typer.Option("SPY", help="Ticker symbol to evaluate.")) -> None:
    """Run a single pipeline iteration for ``symbol`` and print the results."""

    config = load_config()
    runner = build_pipeline(symbol, config)
    now = datetime.utcnow()
    result = runner.run_once(now)
    typer.echo(result)


if __name__ == "__main__":
    app()
