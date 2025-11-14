from datetime import datetime

import pytest

from engines.inputs.data_ingestion_engine import (
    DataIngestionEngine,
    DataIngestionError,
    MarketDataProvider,
    ProviderResponse,
)


class _MockProvider(MarketDataProvider):
    name = "mock"

    def __init__(self, *, options, trades, news, orderbook=None, fundamentals=None):
        self._options = options
        self._trades = trades
        self._news = news
        self._orderbook = orderbook
        self._fundamentals = fundamentals

    def fetch_options_chain(self, symbol: str) -> ProviderResponse:
        return ProviderResponse(self._options)

    def fetch_trades(self, symbol: str) -> ProviderResponse:
        return ProviderResponse(self._trades)

    def fetch_news(self, symbol: str) -> ProviderResponse:
        return ProviderResponse(self._news)

    def fetch_orderbook(self, symbol: str):
        return self._orderbook

    def fetch_fundamentals(self, symbol: str):
        return self._fundamentals


@pytest.fixture
def sample_payload():
    base_time = datetime.now().timestamp()
    options = [
        {"type": "call", "strike": 450.0, "expiry": base_time + 3600},
        {"type": "put", "strike": 440.0, "expiry": base_time + 7200},
    ]
    trades = [
        {"timestamp": base_time + 2, "price": 449.5, "size": 100},
        {"timestamp": base_time + 1, "price": 449.7, "size": 50},
    ]
    news = [
        {
            "timestamp": base_time - 100,
            "title": "Example headline",
            "sentiment_score": 0.2,
            "source": "UnitTest",
        }
    ]
    orderbook = {"timestamp": base_time, "bids": [], "asks": []}
    fundamentals = {"pe_ratio": 20}
    return options, trades, news, orderbook, fundamentals


def test_fetch_returns_sorted_payload(sample_payload):
    options, trades, news, orderbook, fundamentals = sample_payload
    engine = DataIngestionEngine(
        _MockProvider(
            options=options,
            trades=trades,
            news=news,
            orderbook=orderbook,
            fundamentals=fundamentals,
        )
    )

    raw_inputs = engine.fetch("SPY")

    assert [trade["timestamp"] for trade in raw_inputs.trades] == sorted(
        trade["timestamp"] for trade in trades
    )
    assert raw_inputs.news[0]["timestamp"] <= news[0]["timestamp"]
    assert raw_inputs.orderbook == orderbook
    assert raw_inputs.fundamentals == fundamentals


def test_fetch_raises_on_missing_fields(sample_payload):
    options, trades, news, *_ = sample_payload
    bad_options = options + [{"type": "call", "strike": 455.0}]
    engine = DataIngestionEngine(
        _MockProvider(options=bad_options, trades=trades, news=news)
    )

    with pytest.raises(DataIngestionError) as exc:
        engine.fetch("SPY")

    assert "options_chain" in str(exc.value)


def test_fetch_raises_on_empty_sections(sample_payload):
    options, trades, news, *_ = sample_payload
    engine = DataIngestionEngine(
        _MockProvider(options=options, trades=[], news=news)
    )

    with pytest.raises(DataIngestionError) as exc:
        engine.fetch("SPY")

    assert "trades:empty" in str(exc.value)
