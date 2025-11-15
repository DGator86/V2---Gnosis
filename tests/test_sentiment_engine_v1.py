from __future__ import annotations

from datetime import datetime

from engines.inputs.stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter
from engines.sentiment.processors import FlowSentimentProcessor, NewsSentimentProcessor, TechnicalSentimentProcessor
from engines.sentiment.sentiment_engine_v1 import SentimentEngineV1


def test_sentiment_engine_fuses_processors() -> None:
    processors = [
        NewsSentimentProcessor(StaticNewsAdapter(), {}),
        FlowSentimentProcessor({"flow_bias": 0.3}),
        TechnicalSentimentProcessor(StaticMarketDataAdapter(), {"lookback": 10}),
    ]
    engine = SentimentEngineV1(processors, {})
    output = engine.run("SPY", datetime.utcnow())
    assert output.kind == "sentiment"
    assert -1.0 <= output.features["sentiment_score"] <= 1.0
    assert output.features["sentiment_energy"] >= 0.0
