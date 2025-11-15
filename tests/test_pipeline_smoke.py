from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agents.composer.composer_agent_v1 import ComposerAgentV1
from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from engines.elasticity.elasticity_engine_v1 import ElasticityEngineV1
from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.inputs.stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.orchestration.pipeline_runner import PipelineRunner
from engines.sentiment.processors import FlowSentimentProcessor, NewsSentimentProcessor, TechnicalSentimentProcessor
from engines.sentiment.sentiment_engine_v1 import SentimentEngineV1
from ledger.ledger_store import LedgerStore
from trade.trade_agent_v1 import TradeAgentV1


def test_pipeline_smoke(tmp_path: Path) -> None:
    options_adapter = StaticOptionsAdapter()
    market_adapter = StaticMarketDataAdapter()
    news_adapter = StaticNewsAdapter()

    engines = {
        "hedge": HedgeEngineV3(options_adapter, {}),
        "liquidity": LiquidityEngineV1(market_adapter, {}),
        "sentiment": SentimentEngineV1(
            [
                NewsSentimentProcessor(news_adapter, {}),
                FlowSentimentProcessor({"flow_bias": 0.2}),
                TechnicalSentimentProcessor(market_adapter, {"lookback": 14}),
            ],
            {},
        ),
        "elasticity": ElasticityEngineV1(market_adapter, {}),
    }

    primary_agents = {
        "primary_hedge": HedgeAgentV3({}),
        "primary_liquidity": LiquidityAgentV1({}),
        "primary_sentiment": SentimentAgentV1({}),
    }

    composer = ComposerAgentV1({"primary_hedge": 1.0, "primary_liquidity": 1.0, "primary_sentiment": 1.0}, {})
    trade_agent = TradeAgentV1(options_adapter, {"min_confidence": 0.1})

    ledger_store = LedgerStore(tmp_path / "ledger.jsonl")

    runner = PipelineRunner(
        symbol="SPY",
        engines=engines,
        primary_agents=primary_agents,
        composer=composer,
        trade_agent=trade_agent,
        ledger_store=ledger_store,
        config={},
    )

    now = datetime.utcnow()
    result = runner.run_once(now)
    assert result["snapshot"].symbol == "SPY"
    assert result["trade_ideas"], "Trade ideas should be generated"
