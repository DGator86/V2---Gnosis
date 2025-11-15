from __future__ import annotations

"""Command line entrypoint for Super Gnosis pipeline."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import typer

from agents.composer.composer_agent_v1 import ComposerAgentV1
from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from agents.trade_agent_v1 import TradeAgentV1
from agents.base import PrimaryAgent
from engines.elasticity.elasticity_engine_v1 import ElasticityEngineV1
from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.inputs.market_data_adapter import MarketDataAdapter
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from engines.inputs.news_adapter import NewsAdapter
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.orchestration.pipeline_runner import PipelineRunner
from engines.sentiment.processors import FlowSentimentProcessor, NewsSentimentProcessor, TechnicalSentimentProcessor
from engines.sentiment.sentiment_engine_v1 import SentimentEngineV1
from ledger.ledger_store import LedgerStore

app = typer.Typer(help="Super Gnosis / DHPE Pipeline CLI")


def build_pipeline(symbol: str, config: Dict[str, Any]) -> PipelineRunner:
    options_adapter: OptionsChainAdapter = config["adapters"]["options"]
    market_adapter: MarketDataAdapter = config["adapters"]["market"]
    news_adapter: NewsAdapter = config["adapters"]["news"]

    engines = {
        "hedge": HedgeEngineV3(options_adapter, config.get("hedge", {})),
        "liquidity": LiquidityEngineV1(market_adapter, config.get("liquidity", {})),
        "sentiment": SentimentEngineV1(
            [
                NewsSentimentProcessor(news_adapter, config.get("news_sentiment", {})),
                FlowSentimentProcessor(config.get("flow_sentiment", {})),
                TechnicalSentimentProcessor(market_adapter, config.get("technical_sentiment", {})),
            ],
            config.get("sentiment", {}),
        ),
        "elasticity": ElasticityEngineV1(market_adapter, config.get("elasticity", {})),
    }

    primary_agents: Dict[str, PrimaryAgent] = {
        "primary_hedge": HedgeAgentV3(config.get("agents", {}).get("hedge", {})),
        "primary_liquidity": LiquidityAgentV1(config.get("agents", {}).get("liquidity", {})),
        "primary_sentiment": SentimentAgentV1(config.get("agents", {}).get("sentiment", {})),
    }

    composer = ComposerAgentV1(config.get("agents", {}).get("composer", {}).get("weights", {}), config)
    trade_agent = TradeAgentV1(options_adapter, config.get("agents", {}).get("trade", {}))

    ledger_path = Path(config.get("ledger_path", "./data/ledger.jsonl"))
    ledger_store = LedgerStore(ledger_path)

    return PipelineRunner(
        symbol=symbol,
        engines=engines,
        primary_agents=primary_agents,
        composer=composer,
        trade_agent=trade_agent,
        ledger_store=ledger_store,
        config=config,
    )


@app.command()
def run_once(symbol: str = typer.Option("SPY")) -> None:
    config: Dict[str, Any] = {
        "adapters": {
            "options": config_stub_options(),
            "market": config_stub_market(),
            "news": config_stub_news(),
        }
    }
    runner = build_pipeline(symbol, config)
    now = datetime.utcnow()
    result = runner.run_once(now)
    typer.echo(result)


def config_stub_options() -> OptionsChainAdapter:  # type: ignore[return-value]
    raise NotImplementedError("Provide a concrete OptionsChainAdapter implementation")


def config_stub_market() -> MarketDataAdapter:  # type: ignore[return-value]
    raise NotImplementedError("Provide a concrete MarketDataAdapter implementation")


def config_stub_news() -> NewsAdapter:  # type: ignore[return-value]
    raise NotImplementedError("Provide a concrete NewsAdapter implementation")


if __name__ == "__main__":
    app()
